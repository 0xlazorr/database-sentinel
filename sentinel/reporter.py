"""sentinel.reporter - Automated Action Audit Logger & System State Overview Generator.

Generates comprehensive health assessments, action audit trails, quarantine metrics,
threat summaries, and executive reports in CLI, Markdown, and JSON formats.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sentinel.engine import DatabaseEngine
from sentinel.security import SecuritySentinel
from sentinel.healer import DatabaseHealer


class SystemReporter:
    """Comprehensive system state inspector, audit logger, and health dashboard generator."""

    def __init__(self, engine: DatabaseEngine):
        self.engine = engine
        self.conn = engine.get_connection()
        self.security = SecuritySentinel(engine)
        self.healer = DatabaseHealer(engine)

    def get_system_overview(self) -> Dict[str, Any]:
        """Compiles a complete, quantitative assessment of the state of the system."""
        cursor = self.conn.cursor()
        tables = self.engine.get_tables()

        # 1. Table & Storage Metrics
        table_stats = {}
        total_records = 0
        total_indexes = 0
        for tbl in tables:
            r_count = self.engine.get_row_count(tbl)
            idxs = self.engine.get_indexes(tbl)
            table_stats[tbl] = {
                "rows": r_count,
                "indexes": len(idxs)
            }
            total_records += r_count
            total_indexes += len(idxs)

        # 2. Actions & Healing Statistics
        cursor.execute("SELECT COUNT(*) FROM _system_actions_log;")
        total_actions = cursor.fetchone()[0]

        cursor.execute("SELECT action_type, COUNT(*) FROM _system_actions_log GROUP BY action_type;")
        action_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

        # 3. Quarantine Statistics
        cursor.execute("SELECT COUNT(*) FROM _quarantine_records;")
        total_quarantine = cursor.fetchone()[0]

        cursor.execute("SELECT status, COUNT(*) FROM _quarantine_records GROUP BY status;")
        quarantine_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

        # 4. Security Threats
        security_stats = self.security.get_security_overview()

        # 5. Diagnostic Flaws Scan
        flaws_diagnostic = self.healer.diagnose_database()

        # 6. Compute System Health Score (0 - 100)
        # Deductions:
        # - 5 points per unindexed foreign key flaw
        # - 10 points per unresolved quarantine record
        # - 15 points per critical security incident
        # - 10 points per orphan foreign key
        deductions = (
            len(flaws_diagnostic["missing_indexes"]) * 5 +
            total_quarantine * 5 +
            security_stats["severity_breakdown"].get("CRITICAL", 0) * 15 +
            len(flaws_diagnostic["orphan_foreign_keys"]) * 10 +
            len(flaws_diagnostic["negative_numerical_flaws"]) * 10
        )
        health_score = max(0, min(100, 100 - deductions))

        db_file = Path(self.engine.db_path)
        db_size_kb = (db_file.stat().st_size / 1024.0) if db_file.exists() else 0.0

        return {
            "timestamp": datetime.now().isoformat(),
            "database_file": str(self.engine.db_path),
            "database_size_kb": round(db_size_kb, 2),
            "health_score": health_score,
            "health_status": "EXCELLENT" if health_score >= 90 else ("WARNING" if health_score >= 70 else "CRITICAL"),
            "storage_summary": {
                "user_tables_count": len(tables),
                "total_rows": total_records,
                "total_indexes": total_indexes,
                "tables": table_stats
            },
            "autonomous_actions": {
                "total_actions_logged": total_actions,
                "breakdown": action_breakdown
            },
            "quarantine_summary": {
                "total_quarantined": total_quarantine,
                "breakdown": quarantine_breakdown
            },
            "security_summary": security_stats,
            "flaw_diagnostics": flaws_diagnostic
        }

    def get_recent_actions(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Retrieves the recent autonomous action audit trail."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT action_id, action_type, target_table, target_id, details, status, executed_at
            FROM _system_actions_log
            ORDER BY action_id DESC
            LIMIT ?;
        """, (limit,))
        return [dict(r) for r in cursor.fetchall()]

    def render_console_dashboard(self) -> str:
        """Renders an executive ASCII dashboard displaying system state overview."""
        overview = self.get_system_overview()
        score = overview["health_score"]
        status = overview["health_status"]

        lines = [
            "=" * 78,
            "                   DATABASE SENTINEL: SYSTEM STATE OVERVIEW",
            "=" * 78,
            f"Database Target : {overview['database_file']} ({overview['database_size_kb']} KB)",
            f"Health Score    : {score}/100 [{status}]",
            f"Threat Level    : {overview['security_summary']['threat_level']}",
            "-" * 78,
            "RELATIONAL STORAGE INVENTORY:",
            f"  User Tables   : {overview['storage_summary']['user_tables_count']} tables",
            f"  Total Records : {overview['storage_summary']['total_rows']} rows",
            f"  Total Indexes : {overview['storage_summary']['total_indexes']} indexes",
        ]

        for tbl, s in overview["storage_summary"]["tables"].items():
            lines.append(f"    &bull; {tbl:<20} {s['rows']} rows | {s['indexes']} indexes")

        lines.extend([
            "-" * 78,
            "AUTONOMOUS ACTIONS & REMEDIATION LOG:",
            f"  Total Logged  : {overview['autonomous_actions']['total_actions_logged']} actions executed",
        ])
        for act, cnt in overview["autonomous_actions"]["breakdown"].items():
            lines.append(f"    &bull; {act:<30} : {cnt}")

        lines.extend([
            "-" * 78,
            "QUARANTINE & RELATIONAL INTEGRITY:",
            f"  Quarantined   : {overview['quarantine_summary']['total_quarantined']} corrupted/orphan records isolated",
            "-" * 78,
            "SECURITY SENTINEL & ANOMALY DETECTION:",
            f"  Incidents     : {overview['security_summary']['total_incidents_detected']} threats intercepted",
        ])
        for sev, cnt in overview["security_summary"]["severity_breakdown"].items():
            lines.append(f"    &bull; [{sev}] : {cnt}")

        lines.append("=" * 78)
        return "\n".join(lines)

    def export_markdown_report(self, output_path: str = "reports/system_health_report.md") -> str:
        """Exports an executive Markdown health and activity report."""
        overview = self.get_system_overview()
        recent_actions = self.get_recent_actions(10)
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        md = [
            "# Database Sentinel: Comprehensive System State Overview",
            f"**Generated:** {overview['timestamp']}  ",
            f"**Database:** `{overview['database_file']}` ({overview['database_size_kb']} KB)  ",
            f"**Overall Health Score:** **{overview['health_score']}/100** (`{overview['health_status']}`)  ",
            f"**Security Threat Level:** **{overview['security_summary']['threat_level']}**  \n",
            "---",
            "## 1. Storage Inventory",
            "| Table Name | Row Count | Indexes Defined |",
            "| :--- | :---: | :---: |"
        ]

        for tbl, s in overview["storage_summary"]["tables"].items():
            md.append(f"| `{tbl}` | {s['rows']} | {s['indexes']} |")

        md.extend([
            "\n---",
            "## 2. Autonomous Remediation & Actions Executed",
            f"**Total Logged Actions:** {overview['autonomous_actions']['total_actions_logged']}\n",
            "| Action Type | Frequency |",
            "| :--- | :---: |"
        ])
        for act, cnt in overview["autonomous_actions"]["breakdown"].items():
            md.append(f"| `{act}` | {cnt} |")

        md.extend([
            "\n---",
            "## 3. Quarantine & Relational Integrity",
            f"**Total Isolated Corrupt Records:** {overview['quarantine_summary']['total_quarantined']}\n",
            "---",
            "## 4. Security Threat & Anomaly Incidents",
            f"**Total Intercepted Incidents:** {overview['security_summary']['total_incidents_detected']}\n",
            "| Incident ID | Threat Type | Severity | Status | Timestamp |",
            "| :---: | :--- | :---: | :---: | :--- |"
        ])
        for inc in overview["security_summary"]["recent_incidents"]:
            md.append(f"| {inc['incident_id']} | `{inc['threat_type']}` | **{inc['severity']}** | `{inc['mitigation_status']}` | {inc['detected_at']} |")

        md.extend([
            "\n---",
            "## 5. Recent Autonomous Audit Trail",
            "| Action ID | Type | Target Table | Target ID | Details | Time |",
            "| :---: | :--- | :--- | :---: | :--- | :--- |"
        ])
        for a in recent_actions:
            md.append(f"| {a['action_id']} | `{a['action_type']}` | `{a['target_table']}` | `{a.get('target_id') or '-'}` | {a['details']} | {a['executed_at']} |")

        content = "\n".join(md)
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(content)

        return str(out_file)
