#!/usr/bin/env python3
"""sentinel.py - Unified Administrative CLI for Autonomous Database Self-Healing & Reconciliation.

Provides unified command-line control for automatic dataset reconciliation, flaw healing,
action logging, security threat detection, and comprehensive system state reporting.
"""

import sys
import os
import argparse
import json
import time
from pathlib import Path

# Ensure package root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sentinel.engine import DatabaseEngine
from sentinel.reconciler import DatasetReconciler
from sentinel.healer import DatabaseHealer
from sentinel.security import SecuritySentinel
from sentinel.reporter import SystemReporter


def get_default_engine(db_path: str = "sentinel_store.db") -> DatabaseEngine:
    return DatabaseEngine(db_path=db_path)


def cmd_init(args):
    """Initializes schema and optionally loads enterprise demo dataset."""
    engine = get_default_engine(args.db)
    print(f"Database Sentinel initialized successfully: {args.db}")

    if args.seed:
        seed_path = Path(__file__).parent / "data" / "seed_demo.sql"
        if seed_path.exists():
            with open(seed_path, "r", encoding="utf-8") as f:
                engine.execute_script(f.read())
            print("Loaded enterprise demonstration seed records (customers, accounts, orders, ledger).")
        else:
            print("Warning: Seed script not found at data/seed_demo.sql")


def cmd_status(args):
    """Displays the comprehensive system state overview dashboard."""
    engine = get_default_engine(args.db)
    reporter = SystemReporter(engine)
    dashboard = reporter.render_console_dashboard()
    print(dashboard)


def cmd_heal(args):
    """Executes autonomous self-healing: repairs balances, adds indexes, quarantines flaws."""
    engine = get_default_engine(args.db)
    healer = DatabaseHealer(engine)
    print("Initiating autonomous diagnostic scan and self-healing cycle...")
    
    results = healer.auto_heal_all()
    print("\n" + "=" * 65)
    print("AUTONOMOUS SELF-HEALING CYCLE COMPLETE")
    print("=" * 65)
    print(f"Status                    : {results['status']}")
    print(f"Total Flaws Remediated    : {results['total_flaws_repaired']}")
    print(f"Performance Indexes Added : {len(results['indexes_created'])} {results['indexes_created']}")
    print(f"Dangling FKs Healed       : {sum(results['orphan_foreign_keys_healed'].values())}")
    print(f"Illegal Negatives Cleared : {results['negative_flaws_remediated']}")
    print(f"Ledger Balances Repaired  : {results['ledger_balances_repaired']}")
    print("=" * 65 + "\n")


def cmd_reconcile(args):
    """Reconciles an incoming dataset into the specified target table."""
    engine = get_default_engine(args.db)
    reconciler = DatasetReconciler(engine)

    csv_file = args.source
    tbl = args.table
    print(f"Reconciling external dataset '{csv_file}' into relation '{tbl}'...")

    try:
        metrics = reconciler.reconcile_from_csv(tbl, csv_file, key_column=args.key)
        print("\n" + "=" * 65)
        print("DATASET RECONCILIATION SUMMARY")
        print("=" * 65)
        print(f"Total Processed       : {metrics['total_processed']}")
        print(f"New Records Inserted  : {metrics['inserted']}")
        print(f"Drift State Updated   : {metrics['drift_updated']}")
        print(f"Identical Duplicates  : {metrics['identical_duplicates']}")
        print(f"Quarantined Orphans   : {metrics['quarantined_orphans']}")
        print(f"Quarantined Corrupt   : {metrics['quarantined_invalid']}")
        print(f"Actions Audit Logged  : {metrics['actions_logged']}")
        print("=" * 65 + "\n")
    except Exception as err:
        print(f"Reconciliation error: {err}")
        sys.exit(1)


def cmd_security(args):
    """Executes a security threat audit or inspects a specific payload string."""
    engine = get_default_engine(args.db)
    security = SecuritySentinel(engine)

    if args.payload:
        print(f"Analyzing payload for security threats: {args.payload}")
        is_safe, desc, severity = security.inspect_query(args.payload, actor="cli_client")
        if is_safe:
            print("[SAFE] Payload contains no known SQL injection or anomaly signatures.")
        else:
            print(f"[BLOCKED] THREAT DETECTED: {desc} (Severity: {severity})")
            print("Incident logged to _security_incidents table.")
    else:
        overview = security.get_security_overview()
        print("\n" + "=" * 65)
        print("DATABASE SECURITY SENTINEL OVERVIEW")
        print("=" * 65)
        print(f"Active Threat Level : {overview['threat_level']}")
        print(f"Total Interceptions : {overview['total_incidents_detected']}")
        print("Breakdown by Severity:")
        for sev, cnt in overview["severity_breakdown"].items():
            print(f"  [{sev}] : {cnt}")
        print("\nRecent Threat Incidents Logged:")
        for inc in overview["recent_incidents"]:
            print(f"  - Incident #{inc['incident_id']} [{inc['severity']}]: {inc['threat_type']} -> {inc['mitigation_status']}")
        print("=" * 65 + "\n")


def cmd_report(args):
    """Generates and exports an executive Markdown health and activity report."""
    engine = get_default_engine(args.db)
    reporter = SystemReporter(engine)
    out_path = args.output or "reports/system_health_report.md"
    fpath = reporter.export_markdown_report(out_path)
    print(f"Executive System State Overview exported to: {fpath}")


def cmd_daemon(args):
    """Runs autonomous continuous reconciliation and self-healing loop."""
    engine = get_default_engine(args.db)
    healer = DatabaseHealer(engine)
    interval = args.interval or 10
    print(f"Starting Database Sentinel Daemon (scan interval: {interval}s). Press Ctrl+C to stop.")

    try:
        cycle = 1
        while True:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Cycle #{cycle}: Scanning and auto-healing...")
            results = healer.auto_heal_all()
            if results["total_flaws_repaired"] > 0:
                print(f"  -> Repaired {results['total_flaws_repaired']} flaws.")
            else:
                print("  -> System state optimal. 0 flaws detected.")
            cycle += 1
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nDaemon terminated cleanly by operator.")


def main():
    parser = argparse.ArgumentParser(
        description="Database Sentinel: Universal Autonomous Database Self-Healing & Reconciliation Engine."
    )
    parser.add_argument("--db", default="sentinel_store.db", help="Path to database store (default: sentinel_store.db)")

    subparsers = parser.add_subparsers(dest="command", help="Available Sentinel commands")

    # init
    p_init = subparsers.add_parser("init", help="Initialize database and system catalogs")
    p_init.add_argument("--seed", action="store_true", help="Seed with enterprise relational dataset")

    # status
    subparsers.add_parser("status", help="Display comprehensive system state overview")

    # heal
    subparsers.add_parser("heal", help="Scan and auto-heal flaws, balance drift, and missing indexes")

    # reconcile
    p_rec = subparsers.add_parser("reconcile", help="Reconcile external dataset into table")
    p_rec.add_argument("--source", required=True, help="Path to input dataset (CSV)")
    p_rec.add_argument("--table", required=True, help="Target database table")
    p_rec.add_argument("--key", default=None, help="Primary/unique key column")

    # security
    p_sec = subparsers.add_parser("security-audit", help="Run security audit or inspect query")
    p_sec.add_argument("--payload", default=None, help="Inspect query/string for SQLi payloads")

    # report
    p_rep = subparsers.add_parser("report", help="Generate executive health & activity report")
    p_rep.add_argument("--output", default=None, help="Output markdown path")

    # daemon
    p_dae = subparsers.add_parser("daemon", help="Run background continuous watchdog")
    p_dae.add_argument("--interval", type=int, default=10, help="Check interval in seconds")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmd_map = {
        "init": cmd_init,
        "status": cmd_status,
        "heal": cmd_heal,
        "reconcile": cmd_reconcile,
        "security-audit": cmd_security,
        "report": cmd_report,
        "daemon": cmd_daemon
    }

    cmd_map[args.command](args)


if __name__ == "__main__":
    main()
