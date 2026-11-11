"""tests/test_cli.py - Tests for administrative CLI interface."""

import unittest
import tempfile
import subprocess
import sys
from pathlib import Path


class TestSentinelCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.cli_path = Path(__file__).resolve().parent.parent / "sentinel.py"

    def tearDown(self):
        Path(self.db_path).unlink(missing_ok=True)

    def _run_cli(self, args):
        cmd = [sys.executable, str(self.cli_path), "--db", self.db_path] + args
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_01_cli_init_with_seed(self):
        """Test initializing database with demo seed records via CLI."""
        res = self._run_cli(["init", "--seed"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("initialized successfully", res.stdout)
        self.assertIn("Loaded enterprise demonstration seed records", res.stdout)

    def test_02_cli_status(self):
        """Test status dashboard output via CLI."""
        self._run_cli(["init", "--seed"])
        res = self._run_cli(["status"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("DATABASE SENTINEL: SYSTEM STATE OVERVIEW", res.stdout)
        self.assertIn("Health Score", res.stdout)

    def test_03_cli_heal(self):
        """Test running autonomous self-healing via CLI."""
        self._run_cli(["init", "--seed"])
        res = self._run_cli(["heal"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("AUTONOMOUS SELF-HEALING CYCLE COMPLETE", res.stdout)
        self.assertIn("Performance Indexes Added", res.stdout)

    def test_04_cli_reconcile(self):
        """Test reconciling dataset via CLI."""
        self._run_cli(["init", "--seed"])
        csv_path = Path(__file__).resolve().parent.parent / "data" / "sample_incoming_customers.csv"
        res = self._run_cli(["reconcile", "--source", str(csv_path), "--table", "customers", "--key", "customer_code"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("DATASET RECONCILIATION SUMMARY", res.stdout)
        self.assertIn("New Records Inserted", res.stdout)

    def test_05_cli_security_payload_scan(self):
        """Test inspecting malicious SQL injection payload via CLI."""
        res = self._run_cli(["security-audit", "--payload", "' OR 1=1 --"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("[BLOCKED] THREAT DETECTED", res.stdout)

    def test_06_cli_security_benign_scan(self):
        """Test inspecting clean payload via CLI."""
        res = self._run_cli(["security-audit", "--payload", "regular_username"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("[SAFE]", res.stdout)

    def test_07_cli_report_export(self):
        """Test exporting report via CLI."""
        self._run_cli(["init", "--seed"])
        out_file = Path(tempfile.gettempdir()) / "cli_report_test.md"
        res = self._run_cli(["report", "--output", str(out_file)])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(out_file.exists())
        out_file.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
