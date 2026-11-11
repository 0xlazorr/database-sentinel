"""tests/test_engine.py - Tests for DatabaseEngine and catalog introspection."""

import unittest
import tempfile
import sqlite3
from pathlib import Path

from sentinel.engine import DatabaseEngine


class TestDatabaseEngine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.engine = DatabaseEngine(self.db_path)

    def tearDown(self):
        self.engine.close()
        Path(self.db_path).unlink(missing_ok=True)

    def test_01_system_catalogs_initialized(self):
        """Test that internal metadata catalogs exist upon initialization."""
        conn = self.engine.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        self.assertIn("_system_actions_log", tables)
        self.assertIn("_quarantine_records", tables)
        self.assertIn("_security_incidents", tables)

    def test_02_introspection_tables_and_columns(self):
        """Test schema introspection of user tables and column definitions."""
        self.engine.execute_script("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL
            );
        """)
        tables = self.engine.get_tables()
        self.assertEqual(tables, ["users"])

        cols = self.engine.get_columns("users")
        self.assertEqual(len(cols), 3)
        col_names = [c["name"] for c in cols]
        self.assertIn("username", col_names)
        self.assertIn("email", col_names)

    def test_03_introspection_foreign_keys(self):
        """Test introspection of foreign key dependencies."""
        self.engine.execute_script("""
            CREATE TABLE parents (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE children (
                id INTEGER PRIMARY KEY, 
                parent_id INTEGER REFERENCES parents(id) ON DELETE CASCADE
            );
        """)
        fks = self.engine.get_foreign_keys("children")
        self.assertEqual(len(fks), 1)
        self.assertEqual(fks[0]["from"], "parent_id")
        self.assertEqual(fks[0]["table"], "parents")
        self.assertEqual(fks[0]["to"], "id")

    def test_04_action_logging(self):
        """Test logging an autonomous action into _system_actions_log."""
        self.engine.log_action("TEST_ACTION", "users", target_id="101", details="Manual test log")
        cursor = self.engine.get_connection().cursor()
        cursor.execute("SELECT action_type, target_table, target_id FROM _system_actions_log WHERE action_type='TEST_ACTION'")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "TEST_ACTION")
        self.assertEqual(row[1], "users")
        self.assertEqual(row[2], "101")

    def test_05_quarantine_record(self):
        """Test moving a corrupted record to _quarantine_records."""
        payload = {"username": None, "corrupt_data": True}
        qid = self.engine.quarantine_record("users", payload, reason="Null username violation")
        self.assertGreater(qid, 0)
        cursor = self.engine.get_connection().cursor()
        cursor.execute("SELECT rejection_reason, status FROM _quarantine_records WHERE quarantine_id=?", (qid,))
        row = cursor.fetchone()
        self.assertEqual(row[0], "Null username violation")
        self.assertEqual(row[1], "OPEN")


if __name__ == "__main__":
    unittest.main()
