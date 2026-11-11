"""sentinel.security - Real-time Database Threat Guard & Anomaly Sentinel.

Detects and neutralizes SQL injection attacks, privilege escalation, destructive DDL mutations,
and behavioral transaction anomalies, maintaining an immutable incident registry.
"""

import re
import json
from typing import Any, Dict, List, Optional, Tuple

from sentinel.engine import DatabaseEngine


class SecuritySentinel:
    """Security guard for real-time query threat inspection and anomaly detection."""

    SQLI_PATTERNS = [
        (r";\s*(\bdrop\b|\btruncate\b|\balter\b|\bdelete\b)", "STACKED_DESTRUCTIVE_COMMAND", "CRITICAL"),
        (r"\bexec(\s|\()|\bxp_cmdshell\b", "ARBITRARY_COMMAND_EXECUTION", "CRITICAL"),
        (r"\bpragma\s+writable_schema\b", "SYSTEM_CATALOG_TAMPERING", "CRITICAL"),
        (r"\bunion\b\s+(\ball\b\s+)?\bselect\b", "UNION_BASED_INJECTION", "HIGH"),
        (r"\b(sleep\s*\(|benchmark\s*\(|waitfor\s+delay)\b", "TIME_BASED_BLIND_INJECTION", "HIGH"),
        (r"(\bor\b|\band\b)\s*['\"]?([^\s'\"]+)['\"]?\s*=\s*['\"]?\2['\"]?", "BOOLEAN_INJECTION", "HIGH"),
        (r"\b(or|and)\b\s+true\b", "BOOLEAN_INJECTION", "HIGH"),
        (r"(--|#|\/\*).*$", "SQL_COMMENT_INJECTION", "HIGH")
    ]

    def __init__(self, engine: DatabaseEngine):
        self.engine = engine
        self.conn = engine.get_connection()

    def inspect_query(self, query_text: str, actor: str = "client") -> Tuple[bool, Optional[str], str]:
        """Inspects an incoming query or user-supplied string for injection signatures and exploits.
        
        Returns:
            (is_safe, threat_description, severity)
        """
        clean_text = query_text.strip()
        lower_text = clean_text.lower()

        for pattern, threat_name, default_severity in self.SQLI_PATTERNS:
            if re.search(pattern, lower_text, re.IGNORECASE):
                severity = default_severity
                self.flag_incident(
                    threat_type=f"SQLI_{threat_name}",
                    query_payload=clean_text,
                    actor=actor,
                    severity=severity,
                    mitigation="BLOCKED"
                )
                return False, f"Malicious payload detected: {threat_name}", severity

        return True, None, "LOW"

    def flag_incident(self, threat_type: str, query_payload: str, actor: str = "system",
                      severity: str = "HIGH", mitigation: str = "FLAGGED") -> int:
        """Registers a security incident into the database sentinel security audit log."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO _security_incidents (
                threat_type, query_payload, actor_context, severity, mitigation_status
            ) VALUES (?, ?, ?, ?, ?);
        """, (threat_type, query_payload, actor, severity, mitigation))
        self.conn.commit()
        return cursor.lastrowid

    def check_mutation_anomaly(self, table_name: str, proposed_operation: str, 
                               affected_row_count: int, total_table_rows: int,
                               actor: str = "system") -> Tuple[bool, Optional[str]]:
        """Detects destructive mass-mutation anomalies (e.g. unconstrained DELETE or DROP)."""
        if total_table_rows > 10 and proposed_operation.upper() == "DELETE":
            # If a delete would wipe out more than 60% of an operational table
            impact_ratio = affected_row_count / total_table_rows
            if impact_ratio > 0.6:
                reason = f"Abnormal mass deletion detected: attempting to delete {affected_row_count}/{total_table_rows} ({impact_ratio*100:.1f}%) of table '{table_name}'"
                self.flag_incident(
                    threat_type="MASS_DELETION_ANOMALY",
                    query_payload=f"DELETE on {table_name} ({affected_row_count} rows)",
                    actor=actor,
                    severity="HIGH",
                    mitigation="BLOCKED"
                )
                return False, reason

        return True, None

    def get_security_overview(self) -> Dict[str, Any]:
        """Returns active threat level, incident counts by severity, and recent logged threats."""
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM _security_incidents;")
        total_incidents = cursor.fetchone()[0]

        cursor.execute("SELECT severity, COUNT(*) FROM _security_incidents GROUP BY severity;")
        severity_counts = {row[0]: row[1] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT incident_id, threat_type, query_payload, severity, mitigation_status, detected_at
            FROM _security_incidents
            ORDER BY incident_id DESC
            LIMIT 10;
        """)
        recent_incidents = [dict(r) for r in cursor.fetchall()]

        # Compute dynamic threat level
        if severity_counts.get("CRITICAL", 0) > 0:
            threat_level = "ELEVATED (RED)"
        elif severity_counts.get("HIGH", 0) > 0:
            threat_level = "MONITORED (AMBER)"
        else:
            threat_level = "NORMAL (GREEN)"

        return {
            "threat_level": threat_level,
            "total_incidents_detected": total_incidents,
            "severity_breakdown": severity_counts,
            "recent_incidents": recent_incidents
        }
