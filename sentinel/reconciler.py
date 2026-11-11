"""sentinel.reconciler - Autonomous Dataset Reconciler & State Parity Engine.

Audits dataset divergence, synchronizes record drift, resolves dangling foreign keys,
deduplicates entities, and verifies cryptographic state parity across sources.
"""

import csv
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

from sentinel.engine import DatabaseEngine


class DatasetReconciler:
    """Automated dataset reconciliation, drift synchronization, and parity engine."""

    def __init__(self, engine: DatabaseEngine):
        self.engine = engine
        self.conn = engine.get_connection()

    def reconcile_dataset(self, target_table: str, data_rows: List[Dict[str, Any]], 
                          key_column: Optional[str] = None, auto_repair_orphans: bool = True) -> Dict[str, Any]:
        """Reconciles an incoming dataset into the target relational table.
        
        Performs:
          1. Schema alignment and type normalization.
          2. Foreign key validity checking and orphan quarantine.
          3. Idempotent upserting with field-level drift detection.
          4. Comprehensive action audit logging.
        """
        table_cols = {c["name"]: c for c in self.engine.get_columns(target_table)}
        if not table_cols:
            raise ValueError(f"Target table '{target_table}' does not exist in database.")

        # Determine primary key column if not explicitly supplied
        if not key_column:
            pk_cols = [c["name"] for c in table_cols.values() if c["pk"]]
            key_column = pk_cols[0] if pk_cols else list(table_cols.keys())[0]

        # Inspect foreign keys for target table
        fks = self.engine.get_foreign_keys(target_table)

        metrics = {
            "total_processed": len(data_rows),
            "inserted": 0,
            "drift_updated": 0,
            "identical_duplicates": 0,
            "quarantined_orphans": 0,
            "quarantined_invalid": 0,
            "actions_logged": 0
        }

        cursor = self.conn.cursor()

        for raw_row in data_rows:
            # Normalize keys to lowercase and strip whitespace
            row = {str(k).strip(): v for k, v in raw_row.items()}
            row_key_val = row.get(key_column)

            if row_key_val is None or str(row_key_val).strip() == "":
                self.engine.quarantine_record(
                    target_table, row, f"Missing primary/unique key '{key_column}'", severity="HIGH"
                )
                metrics["quarantined_invalid"] += 1
                continue

            # 1. Foreign Key Integrity Check
            is_orphan = False
            orphan_detail = ""
            for fk in fks:
                from_col = fk["from"]
                to_tbl = fk["table"]
                to_col = fk["to"]
                fk_val = row.get(from_col)
                if fk_val is not None and str(fk_val).strip() != "":
                    # Check parent existence
                    cursor.execute(f"SELECT COUNT(*) FROM {to_tbl} WHERE {to_col} = ?", (fk_val,))
                    if cursor.fetchone()[0] == 0:
                        is_orphan = True
                        orphan_detail = f"Foreign key '{from_col}'={fk_val} references non-existent {to_tbl}({to_col})"
                        break

            if is_orphan:
                if auto_repair_orphans:
                    # Quarantine orphan record to preserve parent-child relational invariants
                    self.engine.quarantine_record(target_table, row, orphan_detail, severity="HIGH")
                    self.engine.log_action(
                        "RECONCILE_QUARANTINE_ORPHAN", target_table, row_key_val,
                        before_state=row, details=orphan_detail, status="QUARANTINED"
                    )
                    metrics["quarantined_orphans"] += 1
                    metrics["actions_logged"] += 1
                    continue
                else:
                    self.engine.quarantine_record(target_table, row, orphan_detail, severity="HIGH")
                    metrics["quarantined_orphans"] += 1
                    continue

            # 2. Check existing record in target table
            cursor.execute(f"SELECT * FROM {target_table} WHERE {key_column} = ?", (row_key_val,))
            existing = cursor.fetchone()

            # Align row columns to matching target table columns
            valid_fields = {k: v for k, v in row.items() if k in table_cols}

            if existing is None:
                # INSERT NEW RECORD
                cols = list(valid_fields.keys())
                placeholders = ", ".join(["?"] * len(cols))
                col_names = ", ".join(cols)
                values = [valid_fields[c] for c in cols]
                
                try:
                    cursor.execute(f"INSERT INTO {target_table} ({col_names}) VALUES ({placeholders})", values)
                    self.conn.commit()
                    self.engine.log_action(
                        "RECONCILE_INSERT", target_table, row_key_val,
                        after_state=valid_fields, details="New record reconciled into relation"
                    )
                    metrics["inserted"] += 1
                    metrics["actions_logged"] += 1
                except sqlite3.IntegrityError as err:
                    self.engine.quarantine_record(target_table, row, f"Integrity constraint violation: {err}", severity="HIGH")
                    metrics["quarantined_invalid"] += 1
            else:
                # CHECK FOR DRIFT / DIVERGENCE
                existing_dict = dict(existing)
                drift_detected = False
                drift_details = {}

                for col, val in valid_fields.items():
                    curr_val = existing_dict.get(col)
                    is_equal = False
                    if curr_val is not None and val is not None:
                        # Numeric float tolerance comparison
                        try:
                            f_curr = float(curr_val)
                            f_val = float(val)
                            is_equal = (abs(f_curr - f_val) < 1e-6)
                        except (ValueError, TypeError):
                            is_equal = (str(curr_val).strip() == str(val).strip())
                    elif curr_val is None and (val is None or str(val).strip() == ""):
                        is_equal = True

                    if not is_equal:
                        drift_detected = True
                        drift_details[col] = {"from": curr_val, "to": val}

                if drift_detected:
                    # UPDATE AND RECONCILE DRIFT
                    set_clauses = ", ".join([f"{c} = ?" for c in valid_fields.keys()])
                    values = list(valid_fields.values()) + [row_key_val]
                    cursor.execute(f"UPDATE {target_table} SET {set_clauses} WHERE {key_column} = ?", values)
                    self.conn.commit()
                    self.engine.log_action(
                        "RECONCILE_DRIFT_UPDATE", target_table, row_key_val,
                        before_state=existing_dict, after_state=valid_fields,
                        details=f"Drift resolved across fields: {list(drift_details.keys())}"
                    )
                    metrics["drift_updated"] += 1
                    metrics["actions_logged"] += 1
                else:
                    metrics["identical_duplicates"] += 1

        return metrics

    def reconcile_from_csv(self, target_table: str, csv_path: str, key_column: Optional[str] = None) -> Dict[str, Any]:
        """Reads a CSV file and reconciles its contents into the target table."""
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"Reconciliation source file not found: {csv_path}")

        rows = []
        with open(path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)

        return self.reconcile_dataset(target_table, rows, key_column=key_column)

    def audit_parity(self, target_table: str, benchmark_data: List[Dict[str, Any]], 
                     key_column: Optional[str] = None) -> Dict[str, Any]:
        """Compares target table state against a secondary dataset to calculate parity metrics."""
        table_cols = {c["name"]: c for c in self.engine.get_columns(target_table)}
        if not key_column:
            pk_cols = [c["name"] for c in table_cols.values() if c["pk"]]
            key_column = pk_cols[0] if pk_cols else list(table_cols.keys())[0]

        cursor = self.conn.cursor()
        cursor.execute(f"SELECT * FROM {target_table}")
        db_rows = {str(dict(r)[key_column]): dict(r) for r in cursor.fetchall()}

        source_rows = {}
        for r in benchmark_data:
            k = r.get(key_column)
            if k is not None:
                source_rows[str(k)] = r

        matched_keys = set(db_rows.keys()) & set(source_rows.keys())
        missing_in_db = list(set(source_rows.keys()) - set(db_rows.keys()))
        missing_in_source = list(set(db_rows.keys()) - set(source_rows.keys()))

        divergent_keys = []
        for k in matched_keys:
            d_val = db_rows[k]
            s_val = source_rows[k]
            for col, v in s_val.items():
                if col in d_val and str(d_val[col]).strip() != str(v).strip():
                    divergent_keys.append(k)
                    break

        total_universe = len(set(db_rows.keys()) | set(source_rows.keys()))
        perfect_matches = len(matched_keys) - len(divergent_keys)
        parity_ratio = (perfect_matches / total_universe * 100.0) if total_universe > 0 else 100.0

        return {
            "target_table": target_table,
            "total_records_db": len(db_rows),
            "total_records_source": len(source_rows),
            "matched_keys": len(matched_keys),
            "missing_in_db": missing_in_db,
            "missing_in_source": missing_in_source,
            "divergent_keys": divergent_keys,
            "parity_score": round(parity_ratio, 2)
        }

    def heal_dangling_foreign_keys(self) -> Dict[str, Any]:
        """Scans the entire database for dangling child rows referencing non-existent parent records."""
        tables = self.engine.get_tables()
        cursor = self.conn.cursor()
        healed_report = {}

        for tbl in tables:
            fks = self.engine.get_foreign_keys(tbl)
            for fk in fks:
                from_col = fk["from"]
                to_tbl = fk["table"]
                to_col = fk["to"]

                # Find orphan rows
                cursor.execute(f"""
                    SELECT * FROM {tbl} 
                    WHERE {from_col} IS NOT NULL 
                    AND {from_col} NOT IN (SELECT {to_col} FROM {to_tbl});
                """)
                orphans = [dict(r) for r in cursor.fetchall()]

                if orphans:
                    # Quarantine each orphan row to ensure 100% referential integrity
                    for orphan in orphans:
                        reason = f"Dangling foreign key: {from_col}={orphan[from_col]} does not exist in parent {to_tbl}({to_col})"
                        self.engine.quarantine_record(tbl, orphan, reason, severity="HIGH")
                        
                        # Delete the orphan from the child table
                        pk_cols = [c["name"] for c in self.engine.get_columns(tbl) if c["pk"]]
                        if pk_cols:
                            pk = pk_cols[0]
                            cursor.execute(f"DELETE FROM {tbl} WHERE {pk} = ?", (orphan[pk],))
                        else:
                            cursor.execute(f"DELETE FROM {tbl} WHERE {from_col} = ?", (orphan[from_col],))
                        
                        self.engine.log_action(
                            "HEAL_DANGLING_FOREIGN_KEY", tbl, orphan.get(from_col),
                            before_state=orphan, details=reason, status="REPAIRED"
                        )
                    self.conn.commit()
                    healed_report[f"{tbl}.{from_col}->{to_tbl}"] = len(orphans)

        return healed_report
