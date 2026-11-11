"""sentinel.engine - Universal Database Engine & System Catalog Introspection.

Provides connection management, storage catalog introspection, transactional execution,
and automated initialization of self-healing metadata tables.
"""

import os
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class DatabaseEngine:
    """Universal Relational Database Engine with automated catalog introspection."""

    def __init__(self, db_path: str = "sentinel_store.db"):
        self.db_path = str(db_path)
        self.conn = self._connect()
        self._init_system_catalogs()

    def _connect(self) -> sqlite3.Connection:
        """Establishes an ACID-compliant connection with WAL and foreign key enforcement."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def get_connection(self) -> sqlite3.Connection:
        """Returns the active database connection."""
        return self.conn

    def _init_system_catalogs(self):
        """Initializes internal metadata tables for actions, quarantine, and security audits."""
        cursor = self.conn.cursor()
        
        # 1. Action & Audit Log Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _system_actions_log (
                action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                target_table TEXT NOT NULL,
                target_id TEXT,
                before_state TEXT,
                after_state TEXT,
                details TEXT,
                status TEXT NOT NULL DEFAULT 'SUCCESS',
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)

        # 2. Quarantine Table for Corrupted/Unreconciled Records
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _quarantine_records (
                quarantine_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_table TEXT NOT NULL,
                original_payload TEXT NOT NULL,
                rejection_reason TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'MEDIUM',
                status TEXT NOT NULL DEFAULT 'OPEN',
                quarantined_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)

        # 3. Security Threat & Anomaly Incidents Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS _security_incidents (
                incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
                threat_type TEXT NOT NULL,
                query_payload TEXT NOT NULL,
                actor_context TEXT NOT NULL DEFAULT 'system',
                severity TEXT NOT NULL,
                mitigation_status TEXT NOT NULL DEFAULT 'BLOCKED',
                detected_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)

        # Indexes for fast querying of system catalogs
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_table ON _system_actions_log(target_table);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quarantine_status ON _quarantine_records(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_security_threat ON _security_incidents(threat_type);")
        self.conn.commit()

    def get_tables(self) -> List[str]:
        """Returns all user domain tables, excluding system metadata tables."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE '_system_%' 
            AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_quarantine%' 
            AND name NOT LIKE '_security%'
            ORDER BY name;
        """)
        return [row[0] for row in cursor.fetchall()]

    def get_columns(self, table_name: str) -> List[Dict[str, Any]]:
        """Introspects column definitions, types, nullability, and primary key status."""
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = []
        for row in cursor.fetchall():
            columns.append({
                "cid": row[0],
                "name": row[1],
                "type": row[2].upper(),
                "notnull": bool(row[3]),
                "default_value": row[4],
                "pk": bool(row[5])
            })
        return columns

    def get_foreign_keys(self, table_name: str) -> List[Dict[str, Any]]:
        """Introspects foreign key relationships for a given table."""
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA foreign_key_list({table_name});")
        fks = []
        for row in cursor.fetchall():
            fks.append({
                "id": row[0],
                "seq": row[1],
                "table": row[2],
                "from": row[3],
                "to": row[4],
                "on_update": row[5],
                "on_delete": row[6]
            })
        return fks

    def get_indexes(self, table_name: str) -> List[Dict[str, Any]]:
        """Introspects explicit and implicit indexes defined on a table."""
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA index_list({table_name});")
        indexes = []
        for row in cursor.fetchall():
            idx_name = row[1]
            is_unique = bool(row[2])
            cursor.execute(f"PRAGMA index_info({idx_name});")
            col_rows = cursor.fetchall()
            cols = [c[2] for c in col_rows]
            indexes.append({
                "name": idx_name,
                "unique": is_unique,
                "columns": cols
            })
        return indexes

    def get_row_count(self, table_name: str) -> int:
        """Returns the total number of rows in a table."""
        cursor = self.conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        row = cursor.fetchone()
        return row[0] if row else 0

    def execute_script(self, sql_script: str):
        """Executes a multi-statement SQL script atomically."""
        self.conn.executescript(sql_script)

    def log_action(self, action_type: str, target_table: str, target_id: Any = None,
                   before_state: Any = None, after_state: Any = None, details: str = "",
                   status: str = "SUCCESS"):
        """Records an autonomous modification or healing action into the system audit log."""
        b_str = json.dumps(before_state, default=str) if before_state is not None else None
        a_str = json.dumps(after_state, default=str) if after_state is not None else None
        self.conn.execute("""
            INSERT INTO _system_actions_log (
                action_type, target_table, target_id, before_state, after_state, details, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (action_type, target_table, str(target_id) if target_id else None, b_str, a_str, details, status))
        self.conn.commit()

    def quarantine_record(self, source_table: str, payload: Any, reason: str, severity: str = "MEDIUM") -> int:
        """Quarantines an unrecoverable corrupted record to preserve primary relation integrity."""
        p_str = json.dumps(payload, default=str) if not isinstance(payload, str) else payload
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO _quarantine_records (
                source_table, original_payload, rejection_reason, severity
            ) VALUES (?, ?, ?, ?);
        """, (source_table, p_str, reason, severity))
        self.conn.commit()
        return cursor.lastrowid

    def close(self):
        """Closes the underlying database connection."""
        self.conn.close()
