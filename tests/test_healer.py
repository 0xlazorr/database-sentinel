"""tests/test_healer.py - Tests for DatabaseHealer and autonomous remediation."""

import unittest
import tempfile
from pathlib import Path

from sentinel.engine import DatabaseEngine
from sentinel.healer import DatabaseHealer


class TestDatabaseHealer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.engine = DatabaseEngine(self.db_path)
        self.healer = DatabaseHealer(self.engine)

        # Create financial accounts and transaction ledger
        self.engine.execute_script("""
            CREATE TABLE accounts (
                account_id INTEGER PRIMARY KEY,
                account_name TEXT NOT NULL,
                balance NUMERIC NOT NULL
            );
            CREATE TABLE transactions (
                transaction_id INTEGER PRIMARY KEY,
                account_id INTEGER REFERENCES accounts(account_id),
                amount NUMERIC NOT NULL
            );
        """)

    def tearDown(self):
        self.engine.close()
        Path(self.db_path).unlink(missing_ok=True)

    def test_01_diagnose_unindexed_foreign_key(self):
        """Test diagnostic scanner detects missing indexes on foreign key columns."""
        diag = self.healer.diagnose_database()
        self.assertEqual(len(diag["missing_indexes"]), 1)
        self.assertEqual(diag["missing_indexes"][0]["table"], "transactions")
        self.assertEqual(diag["missing_indexes"][0]["column"], "account_id")

    def test_02_auto_heal_missing_indexes(self):
        """Test autonomous synthesizer generates performance indexes for unindexed foreign keys."""
        created = self.healer.auto_heal_indexes()
        self.assertIn("idx_transactions_account_id", created)

        # Re-diagnosing should show 0 missing indexes
        diag = self.healer.diagnose_database()
        self.assertEqual(len(diag["missing_indexes"]), 0)

    def test_03_reconcile_ledger_balance_discrepancy(self):
        """Test auto-healing detects ledger drift and repairs stored account balance."""
        # Insert account with corrupted stored balance of 100.0
        self.engine.execute_script("INSERT INTO accounts (account_id, account_name, balance) VALUES (1, 'Treasury', 100.0);")
        # Transactions sum to 350.0 (drift = 250.0)
        self.engine.execute_script("""
            INSERT INTO transactions (transaction_id, account_id, amount) VALUES (1, 1, 200.0);
            INSERT INTO transactions (transaction_id, account_id, amount) VALUES (2, 1, 150.0);
        """)

        repairs = self.healer.reconcile_ledger_balances()
        self.assertEqual(len(repairs), 1)
        self.assertEqual(repairs[0]["account_id"], 1)
        self.assertEqual(repairs[0]["previous_balance"], 100.0)
        self.assertEqual(repairs[0]["repaired_balance"], 350.0)

        # Verify stored balance in accounts table was healed
        cursor = self.engine.get_connection().cursor()
        cursor.execute("SELECT balance FROM accounts WHERE account_id=1")
        self.assertEqual(float(cursor.fetchone()[0]), 350.0)

    def test_04_auto_heal_negative_values(self):
        """Test remediating illegal negative numeric values by quarantine."""
        self.engine.execute_script("""
            INSERT INTO accounts (account_id, account_name, balance) VALUES (2, 'Corrupt Account', -500.0);
        """)
        remediated = self.healer.auto_heal_negative_values(quarantine_instead_of_zero=True)
        self.assertEqual(remediated, 1)

        # Verify account was removed from main table and moved to quarantine
        cursor = self.engine.get_connection().cursor()
        cursor.execute("SELECT COUNT(*) FROM accounts WHERE account_id=2")
        self.assertEqual(cursor.fetchone()[0], 0)

        cursor.execute("SELECT COUNT(*) FROM _quarantine_records WHERE source_table='accounts'")
        self.assertEqual(cursor.fetchone()[0], 1)

    def test_05_full_auto_heal_cycle(self):
        """Test executing complete autonomous healing cycle."""
        self.engine.execute_script("INSERT INTO accounts (account_id, account_name, balance) VALUES (10, 'Test Acc', 50.0);")
        self.engine.execute_script("INSERT INTO transactions (transaction_id, account_id, amount) VALUES (101, 10, 50.0);")

        results = self.healer.auto_heal_all()
        self.assertEqual(results["status"], "HEALTH_RESTORED")
        self.assertGreaterEqual(results["total_flaws_repaired"], 1) # Created missing index


if __name__ == "__main__":
    unittest.main()
