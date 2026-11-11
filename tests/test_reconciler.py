"""tests/test_reconciler.py - Tests for DatasetReconciler and parity audits."""

import unittest
import tempfile
import csv
from pathlib import Path

from sentinel.engine import DatabaseEngine
from sentinel.reconciler import DatasetReconciler


class TestDatasetReconciler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.engine = DatabaseEngine(self.db_path)
        self.reconciler = DatasetReconciler(self.engine)

        # Create test tables
        self.engine.execute_script("""
            CREATE TABLE suppliers (
                supplier_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE products (
                sku TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price NUMERIC NOT NULL,
                supplier_id INTEGER REFERENCES suppliers(supplier_id)
            );
        """)
        # Seed parent
        self.engine.execute_script("INSERT INTO suppliers (supplier_id, name) VALUES (1, 'Acme Corp');")

    def tearDown(self):
        self.engine.close()
        Path(self.db_path).unlink(missing_ok=True)

    def test_01_insert_new_records(self):
        """Test reconciling new dataset rows into an empty table."""
        rows = [
            {"sku": "SKU-001", "name": "Widget A", "price": 19.99, "supplier_id": 1},
            {"sku": "SKU-002", "name": "Widget B", "price": 29.99, "supplier_id": 1}
        ]
        metrics = self.reconciler.reconcile_dataset("products", rows, key_column="sku")
        self.assertEqual(metrics["inserted"], 2)
        self.assertEqual(metrics["drift_updated"], 0)
        self.assertEqual(self.engine.get_row_count("products"), 2)

    def test_02_detect_and_update_drift(self):
        """Test detecting field drift in existing records and auto-updating them."""
        # Initial insert
        self.reconciler.reconcile_dataset("products", [
            {"sku": "SKU-001", "name": "Widget A", "price": 19.99, "supplier_id": 1}
        ], key_column="sku")

        # Incoming drift update (price changed from 19.99 to 24.50)
        drift_rows = [
            {"sku": "SKU-001", "name": "Widget A", "price": 24.50, "supplier_id": 1}
        ]
        metrics = self.reconciler.reconcile_dataset("products", drift_rows, key_column="sku")
        self.assertEqual(metrics["inserted"], 0)
        self.assertEqual(metrics["drift_updated"], 1)

        cursor = self.engine.get_connection().cursor()
        cursor.execute("SELECT price FROM products WHERE sku='SKU-001'")
        self.assertEqual(float(cursor.fetchone()[0]), 24.50)

    def test_03_quarantine_orphan_foreign_keys(self):
        """Test quarantining records with invalid foreign keys."""
        orphan_rows = [
            {"sku": "SKU-999", "name": "Ghost Item", "price": 99.00, "supplier_id": 8888} # non-existent supplier 8888
        ]
        metrics = self.reconciler.reconcile_dataset("products", orphan_rows, key_column="sku")
        self.assertEqual(metrics["quarantined_orphans"], 1)
        self.assertEqual(self.engine.get_row_count("products"), 0)

        # Verify quarantine table has the record
        cursor = self.engine.get_connection().cursor()
        cursor.execute("SELECT COUNT(*) FROM _quarantine_records WHERE source_table='products'")
        self.assertEqual(cursor.fetchone()[0], 1)

    def test_04_audit_parity_scoring(self):
        """Test mathematical parity scoring between database state and external dataset."""
        self.reconciler.reconcile_dataset("products", [
            {"sku": "SKU-001", "name": "Item 1", "price": 10.0, "supplier_id": 1},
            {"sku": "SKU-002", "name": "Item 2", "price": 20.0, "supplier_id": 1}
        ], key_column="sku")

        # Benchmark dataset: 1 match, 1 missing in DB, 1 missing in source
        benchmark = [
            {"sku": "SKU-001", "name": "Item 1", "price": 10.0, "supplier_id": 1}, # Match
            {"sku": "SKU-003", "name": "Item 3", "price": 30.0, "supplier_id": 1}  # Missing in DB
        ]
        parity = self.reconciler.audit_parity("products", benchmark, key_column="sku")
        self.assertEqual(parity["total_records_db"], 2)
        self.assertEqual(parity["total_records_source"], 2)
        self.assertEqual(parity["missing_in_db"], ["SKU-003"])
        self.assertEqual(parity["missing_in_source"], ["SKU-002"])
        self.assertLess(parity["parity_score"], 100.0)

    def test_05_reconcile_from_csv_file(self):
        """Test reconciliation from an external CSV file."""
        csv_file = tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, newline="")
        writer = csv.writer(csv_file)
        writer.writerow(["sku", "name", "price", "supplier_id"])
        writer.writerow(["SKU-100", "CSV Item", 45.0, 1])
        csv_file.close()

        metrics = self.reconciler.reconcile_from_csv("products", csv_file.name, key_column="sku")
        self.assertEqual(metrics["inserted"], 1)
        Path(csv_file.name).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
