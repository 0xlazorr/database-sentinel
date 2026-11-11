"""sentinel.healer - Autonomous Database Self-Healing & Bug Remediation Engine.

Diagnoses storage flaws, repairs ledger balance discrepancies, corrects invalid domain values,
quarantines corrupt records, and automatically synthesizes missing performance indexes.
"""

import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from sentinel.engine import DatabaseEngine


class DatabaseHealer:
    """Autonomous self-healing engine for detecting and remediating database bugs and flaws."""

    def __init__(self, engine: DatabaseEngine):
        self.engine = engine
        self.conn = engine.get_connection()

    def diagnose_database(self) -> Dict[str, Any]:
        """Performs a comprehensive diagnostic scan across all relations for flaws and anomalies."""
        tables = self.engine.get_tables()
        diagnostics = {
            "tables_scanned": len(tables),
            "flaws_detected": 0,
            "missing_indexes": [],
            "orphan_foreign_keys": [],
            "negative_numerical_flaws": [],
            "ledger_imbalances": []
        }

        cursor = self.conn.cursor()

        for tbl in tables:
            cols = self.engine.get_columns(tbl)
            fks = self.engine.get_foreign_keys(tbl)
            indexes = self.engine.get_indexes(tbl)

            # 1. Detect unindexed foreign keys (causes slow sequential joins)
            indexed_columns = set()
            for idx in indexes:
                indexed_columns.update(idx["columns"])

            for fk in fks:
                from_col = fk["from"]
                if from_col not in indexed_columns:
                    diagnostics["missing_indexes"].append({
                        "table": tbl,
                        "column": from_col,
                        "recommendation": f"CREATE INDEX idx_{tbl}_{from_col} ON {tbl}({from_col})"
                    })
                    diagnostics["flaws_detected"] += 1

            # 2. Check for orphan foreign keys
            for fk in fks:
                from_col = fk["from"]
                to_tbl = fk["table"]
                to_col = fk["to"]
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {tbl} 
                    WHERE {from_col} IS NOT NULL 
                    AND {from_col} NOT IN (SELECT {to_col} FROM {to_tbl});
                """)
                orphan_count = cursor.fetchone()[0]
                if orphan_count > 0:
                    diagnostics["orphan_foreign_keys"].append({
                        "table": tbl,
                        "column": from_col,
                        "parent_table": to_tbl,
                        "orphan_count": orphan_count
                    })
                    diagnostics["flaws_detected"] += orphan_count

            # 3. Detect negative balances or quantities where domain requires positive numbers
            for c in cols:
                cname = c["name"].lower()
                ctype = c["type"]
                if any(k in cname for k in ["balance", "quantity", "price", "amount", "inventory", "stock"]):
                    if "INT" in ctype or "NUM" in ctype or "REAL" in ctype or "FLOAT" in ctype:
                        cursor.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {c['name']} < 0;")
                        neg_count = cursor.fetchone()[0]
                        if neg_count > 0:
                            diagnostics["negative_numerical_flaws"].append({
                                "table": tbl,
                                "column": c["name"],
                                "negative_count": neg_count
                            })
                            diagnostics["flaws_detected"] += neg_count

        return diagnostics

    def auto_heal_indexes(self) -> List[str]:
        """Automatically creates missing B-Tree indexes on unindexed foreign key and join columns."""
        tables = self.engine.get_tables()
        cursor = self.conn.cursor()
        created_indexes = []

        for tbl in tables:
            fks = self.engine.get_foreign_keys(tbl)
            indexes = self.engine.get_indexes(tbl)
            indexed_columns = set()
            for idx in indexes:
                indexed_columns.update(idx["columns"])

            for fk in fks:
                col = fk["from"]
                if col not in indexed_columns:
                    idx_name = f"idx_{tbl}_{col}"
                    sql = f"CREATE INDEX IF NOT EXISTS {idx_name} ON {tbl}({col});"
                    cursor.execute(sql)
                    self.conn.commit()
                    created_indexes.append(idx_name)
                    self.engine.log_action(
                        "HEAL_CREATE_INDEX", tbl, None,
                        after_state={"index": idx_name, "column": col},
                        details=f"Auto-generated performance index to eliminate sequential scans"
                    )

        return created_indexes

    def auto_heal_negative_values(self, quarantine_instead_of_zero: bool = True) -> int:
        """Remediates illegal negative numeric values in domain columns."""
        tables = self.engine.get_tables()
        cursor = self.conn.cursor()
        healed_count = 0

        for tbl in tables:
            cols = self.engine.get_columns(tbl)
            pk_cols = [c["name"] for c in cols if c["pk"]]
            pk = pk_cols[0] if pk_cols else None

            for c in cols:
                cname = c["name"].lower()
                col_real_name = c["name"]
                if any(k in cname for k in ["balance", "quantity", "inventory", "stock"]):
                    cursor.execute(f"SELECT * FROM {tbl} WHERE {col_real_name} < 0;")
                    flawed_rows = [dict(r) for r in cursor.fetchall()]

                    for row in flawed_rows:
                        row_id = row.get(pk) if pk else row[col_real_name]
                        if quarantine_instead_of_zero:
                            # Quarantine the corrupt record
                            self.engine.quarantine_record(
                                tbl, row, f"Illegal negative value in column '{col_real_name}' ({row[col_real_name]})", severity="HIGH"
                            )
                            if pk:
                                cursor.execute(f"DELETE FROM {tbl} WHERE {pk} = ?", (row[pk],))
                            else:
                                cursor.execute(f"DELETE FROM {tbl} WHERE {col_real_name} = ?", (row[col_real_name],))
                            self.engine.log_action(
                                "HEAL_QUARANTINE_NEGATIVE", tbl, row_id,
                                before_state=row, details=f"Quarantined record with invalid negative {col_real_name}"
                            )
                        else:
                            # Clamp to zero
                            if pk:
                                cursor.execute(f"UPDATE {tbl} SET {col_real_name} = 0 WHERE {pk} = ?", (row[pk],))
                            self.engine.log_action(
                                "HEAL_CLAMP_NEGATIVE", tbl, row_id,
                                before_state=row[col_real_name], after_state=0,
                                details=f"Clamped illegal negative {col_real_name} to 0"
                            )
                        healed_count += 1

        self.conn.commit()
        return healed_count

    def reconcile_ledger_balances(self, accounts_table: str = "accounts", 
                                   transactions_table: str = "transactions",
                                   account_id_col: str = "account_id",
                                   balance_col: str = "balance",
                                   amount_col: str = "amount") -> List[Dict[str, Any]]:
        """Audits and auto-repairs discrepancies between calculated transaction sums and stored balances."""
        cursor = self.conn.cursor()
        
        # Verify tables exist
        tables = self.engine.get_tables()
        if accounts_table not in tables or transactions_table not in tables:
            return []

        repaired_accounts = []
        cursor.execute(f"""
            SELECT a.{account_id_col}, a.{balance_col}, COALESCE(SUM(t.{amount_col}), 0) AS calculated_sum
            FROM {accounts_table} a
            LEFT JOIN {transactions_table} t ON a.{account_id_col} = t.{account_id_col}
            GROUP BY a.{account_id_col}, a.{balance_col};
        """)

        for row in cursor.fetchall():
            acc_id = row[0]
            stored_bal = float(row[1] or 0.0)
            calc_sum = float(row[2] or 0.0)

            # Check if discrepancy exists
            if abs(stored_bal - calc_sum) > 0.001:
                # Auto-heal balance to match transaction ledger
                cursor.execute(f"UPDATE {accounts_table} SET {balance_col} = ? WHERE {account_id_col} = ?", (calc_sum, acc_id))
                self.engine.log_action(
                    "HEAL_LEDGER_RECONCILIATION", accounts_table, acc_id,
                    before_state={balance_col: stored_bal},
                    after_state={balance_col: calc_sum},
                    details=f"Auto-healed ledger drift discrepancy of {abs(stored_bal - calc_sum):.2f}"
                )
                repaired_accounts.append({
                    "account_id": acc_id,
                    "previous_balance": stored_bal,
                    "repaired_balance": calc_sum,
                    "discrepancy": round(stored_bal - calc_sum, 2)
                })

        self.conn.commit()
        return repaired_accounts

    def auto_heal_all(self) -> Dict[str, Any]:
        """Executes a full autonomous self-healing cycle across all relations."""
        from sentinel.reconciler import DatasetReconciler
        reconciler = DatasetReconciler(self.engine)

        created_indexes = self.auto_heal_indexes()
        healed_orphans = reconciler.heal_dangling_foreign_keys()
        healed_negatives = self.auto_heal_negative_values()
        ledger_repairs = self.reconcile_ledger_balances()

        return {
            "status": "HEALTH_RESTORED",
            "indexes_created": created_indexes,
            "orphan_foreign_keys_healed": healed_orphans,
            "negative_flaws_remediated": healed_negatives,
            "ledger_balances_repaired": len(ledger_repairs),
            "total_flaws_repaired": len(created_indexes) + sum(healed_orphans.values()) + healed_negatives + len(ledger_repairs)
        }
