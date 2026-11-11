"""tests/test_reporter.py - Tests for SystemReporter overview and metrics."""

import unittest
import tempfile
from pathlib import Path

from sentinel.engine import DatabaseEngine
from sentinel.reporter import SystemReporter


class TestSystemReporter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.tmp.name
        self.engine = DatabaseEngine(self.db_path)
        self.reporter = SystemReporter(self.engine)

        self.engine.execute_script("""
            CREATE TABLE inventory (
                item_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                stock INTEGER NOT NULL
            );
            INSERT INTO inventory (item_id, name, stock) VALUES (1, 'Cable', 100);
        """)

    def tearDown(self):
        self.engine.close()
        Path(self.db_path).unlink(missing_ok=True)

    def test_01_health_score_calculation(self):
        """Test health score computation on clean database."""
        overview = self.reporter.get_system_overview()
        self.assertEqual(overview["health_score"], 100)
        self.assertEqual(overview["health_status"], "EXCELLENT")
        self.assertEqual(overview["storage_summary"]["user_tables_count"], 1)
        self.assertEqual(overview["storage_summary"]["total_rows"], 1)

    def test_02_console_dashboard_rendering(self):
        """Test ASCII dashboard output string generation."""
        dashboard = self.reporter.render_console_dashboard()
        self.assertIn("DATABASE SENTINEL: SYSTEM STATE OVERVIEW", dashboard)
        self.assertIn("Health Score", dashboard)
        self.assertIn("inventory", dashboard)

    def test_03_markdown_report_export(self):
        """Test exporting markdown report with table structures."""
        out_f = Path(tempfile.gettempdir()) / "test_md_report.md"
        res = self.reporter.export_markdown_report(str(out_f))
        self.assertTrue(Path(res).exists())
        with open(res, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("# Database Sentinel", content)
        self.assertIn("Health Score", content)
        out_f.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
