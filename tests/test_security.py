"""tests/test_security.py - Tests for SecuritySentinel threat inspection and anomaly detection."""

import unittest
import tempfile
from pathlib import Path

from sentinel.engine import DatabaseEngine
from sentinel.security import SecuritySentinel


class TestSecuritySentinel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.engine = DatabaseEngine(self.db_path)
        self.security = SecuritySentinel(self.engine)

    def tearDown(self):
        self.engine.close()
        Path(self.db_path).unlink(missing_ok=True)

    def test_01_detect_boolean_sqli(self):
        """Test intercepting boolean-based SQL injection bypass payloads."""
        payload = "admin' OR 1=1 --"
        is_safe, desc, severity = self.security.inspect_query(payload, actor="attacker_ip_1")
        self.assertFalse(is_safe)
        self.assertIn("BOOLEAN_INJECTION", desc)
        self.assertEqual(severity, "HIGH")

    def test_02_detect_union_sqli(self):
        """Test intercepting UNION-based data extraction attacks."""
        payload = "1' UNION SELECT id, username, password FROM users --"
        is_safe, desc, severity = self.security.inspect_query(payload, actor="attacker_ip_2")
        self.assertFalse(is_safe)
        self.assertIn("UNION_BASED_INJECTION", desc)

    def test_03_detect_destructive_stacked_commands(self):
        """Test intercepting stacked destructive DDL commands."""
        payload = "valid_user'; DROP TABLE customers; --"
        is_safe, desc, severity = self.security.inspect_query(payload, actor="attacker_ip_3")
        self.assertFalse(is_safe)
        self.assertEqual(severity, "CRITICAL")

    def test_04_allow_benign_queries(self):
        """Test that legitimate queries are passed without false positives."""
        legit_query = "SELECT * FROM orders WHERE customer_id = 45 AND status = 'COMPLETED'"
        is_safe, desc, severity = self.security.inspect_query(legit_query, actor="trusted_app")
        self.assertTrue(is_safe)
        self.assertIsNone(desc)

    def test_05_flag_incident_registry(self):
        """Test that threats are logged into the _security_incidents catalog."""
        self.security.inspect_query("' OR '1'='1", actor="test_actor")
        overview = self.security.get_security_overview()
        self.assertGreaterEqual(overview["total_incidents_detected"], 1)
        self.assertIn(overview["threat_level"], ["MONITORED (AMBER)", "ELEVATED (RED)"])


if __name__ == "__main__":
    unittest.main()
