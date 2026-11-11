"""tests/test_comprehensive.py - End-to-end integration and system state verification."""

import unittest
import tempfile
from pathlib import Path

from sentinel.engine import DatabaseEngine
from sentinel.reconciler import DatasetReconciler
from sentinel.healer import DatabaseHealer
from sentinel.security import SecuritySentinel
from sentinel.reporter import SystemReporter


class TestComprehensiveSentinel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.engine = DatabaseEngine(self.db_path)
        self.reconciler = DatasetReconciler(self.engine)
        self.healer = DatabaseHealer(self.engine)
        self.security = SecuritySentinel(self.engine)
        self.reporter = SystemReporter(self.engine)

        # Load seed schema
        seed_path = Path(__file__).resolve().parent.parent / "data" / "seed_demo.sql"
        if seed_path.exists():
            with open(seed_path, "r", encoding="utf-8") as f:
                self.engine.execute_script(f.read())

    def tearDown(self):
        self.engine.close()
        Path(self.db_path).unlink(missing_ok=True)

    def test_01_end_to_end_seed_and_health_score(self):
        """Test initial state overview and health diagnostics on seeded database."""
        overview = self.reporter.get_system_overview()
        self.assertEqual(overview["storage_summary"]["user_tables_count"], 4) # customers, accounts, transactions, orders
        self.assertLess(overview["health_score"], 100) # seeded with flaws (unindexed FKs, negative balance, ledger drift)

    def test_02_end_to_end_autonomous_healing(self):
        """Test autonomous healing cycle resolves seeded flaws and restores high health score."""
        heal_results = self.healer.auto_heal_all()
        self.assertEqual(heal_results["status"], "HEALTH_RESTORED")
        self.assertGreater(heal_results["total_flaws_repaired"], 0)

        # Confirm ledger drift repaired
        cursor = self.engine.get_connection().cursor()
        cursor.execute("SELECT balance FROM accounts WHERE account_id = 2")
        self.assertEqual(float(cursor.fetchone()[0]), 1500.0) # Repaired from 1200.0 to 1500.0

        # Post-healing health check
        overview = self.reporter.get_system_overview()
        self.assertGreaterEqual(overview["health_score"], 85)

    def test_03_end_to_end_reconciliation_flow(self):
        """Test reconciling incoming CSV data with drift, duplicate, and orphan isolation."""
        csv_customers = Path(__file__).resolve().parent.parent / "data" / "sample_incoming_customers.csv"
        metrics = self.reconciler.reconcile_from_csv("customers", str(csv_customers), key_column="customer_code")
        
        self.assertEqual(metrics["total_processed"], 5)
        self.assertEqual(metrics["inserted"], 2) # CUST-004, CUST-005
        self.assertEqual(metrics["drift_updated"], 1) # CUST-001 email/tier updated
        self.assertEqual(metrics["identical_duplicates"], 1) # CUST-002 skipped
        self.assertEqual(metrics["quarantined_invalid"], 1) # Invalid empty code quarantined

    def test_04_end_to_end_security_threat_block(self):
        """Test security sentinel intercepts injection attack and reflects in system state."""
        sqli = "' OR 1=1 --"
        is_safe, _, _ = self.security.inspect_query(sqli, actor="external_probe")
        self.assertFalse(is_safe)

        overview = self.reporter.get_system_overview()
        self.assertEqual(overview["security_summary"]["total_incidents_detected"], 1)

    def test_05_end_to_end_report_export(self):
        """Test exporting comprehensive executive markdown health report."""
        out_report = Path(tempfile.gettempdir()) / "test_sentinel_report.md"
        generated_path = self.reporter.export_markdown_report(str(out_report))
        self.assertTrue(Path(generated_path).exists())
        self.assertGreater(Path(generated_path).stat().st_size, 200)
        out_report.unlink(missing_ok=True)

    def test_06_orphan_foreign_keys_in_orders_quarantined(self):
        """Test reconciling incoming orders with invalid parent customer is quarantined."""
        csv_orders = Path(__file__).resolve().parent.parent / "data" / "sample_incoming_orders.csv"
        metrics = self.reconciler.reconcile_from_csv("orders", str(csv_orders), key_column="order_code")
        self.assertEqual(metrics["quarantined_orphans"], 1) # ORD-504 with customer 999
        self.assertEqual(metrics["inserted"], 1) # ORD-503
        self.assertEqual(metrics["identical_duplicates"], 1) # ORD-501

    def test_07_time_based_blind_sqli_interception(self):
        """Test intercepting blind SQL injection with sleep/waitfor commands."""
        query = "1; WAITFOR DELAY '0:0:5'--"
        is_safe, desc, sev = self.security.inspect_query(query, actor="scanner")
        self.assertFalse(is_safe)
        self.assertIn("TIME_BASED", desc)

    def test_08_arbitrary_command_execution_blocked(self):
        """Test intercepting xp_cmdshell / exec attempts."""
        query = "EXEC xp_cmdshell('whoami');"
        is_safe, desc, sev = self.security.inspect_query(query, actor="scanner")
        self.assertFalse(is_safe)
        self.assertEqual(sev, "CRITICAL")

    def test_09_mass_deletion_anomaly_detection(self):
        """Test detecting abnormal mass-deletion operations."""
        # Seed 20 dummy customers
        for i in range(10, 30):
            self.engine.get_connection().execute(
                "INSERT INTO customers (customer_code, full_name, email) VALUES (?, ?, ?)",
                (f"CUST-{i}", f"User {i}", f"user{i}@test.com")
            )
        self.engine.get_connection().commit()

        # Attempt to delete 18 out of 23 records (>60%)
        is_safe, reason = self.security.check_mutation_anomaly("customers", "DELETE", 18, 23, actor="rogue_script")
        self.assertFalse(is_safe)
        self.assertIn("Abnormal mass deletion", reason)

    def test_10_idempotency_of_repeated_reconciliation(self):
        """Test that re-running reconciliation produces zero side effects and identical counts."""
        csv_customers = Path(__file__).resolve().parent.parent / "data" / "sample_incoming_customers.csv"
        # Run 1
        m1 = self.reconciler.reconcile_from_csv("customers", str(csv_customers), key_column="customer_code")
        # Run 2 immediately
        m2 = self.reconciler.reconcile_from_csv("customers", str(csv_customers), key_column="customer_code")
        self.assertEqual(m2["inserted"], 0)
        self.assertEqual(m2["drift_updated"], 0)
        self.assertEqual(m2["identical_duplicates"], 4) # All existing valid records matched

    def test_11_recent_actions_retrieval(self):
        """Test retrieving recent audit log history."""
        self.healer.auto_heal_all()
        actions = self.reporter.get_recent_actions(limit=10)
        self.assertGreater(len(actions), 0)
        action_types = [a["action_type"] for a in actions]
        self.assertTrue(any("HEAL_" in t for t in action_types))


if __name__ == "__main__":
    unittest.main()
