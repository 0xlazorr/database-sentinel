# Database Sentinel

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Database Engines](https://img.shields.io/badge/engines-SQLite3%20%7C%20PostgreSQL-green.svg)](https://www.sqlite.org/)
[![Test Suite](https://img.shields.io/badge/tests-41%20passed%20%7C%20100%25-brightgreen.svg)](tests/)
[![Security Sentinel](https://img.shields.io/badge/security-SQLi%20Defense%20%7C%20Anomaly%20Guard-red.svg)](sentinel/security.py)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)

An autonomous, domain-agnostic database self-healing, dataset reconciliation, and security sentinel engine. Engineered to automatically detect and remediate database flaws, reconcile divergent datasets, isolate orphan records, neutralize SQL injection threats, maintain persistent action audit logs, and generate real-time system health assessments.

---

## Table of Contents
1. [System Architecture](#1-system-architecture)
2. [Core Capabilities](#2-core-capabilities)
3. [The Technology Behind Database Sentinel](#3-the-technology-behind-database-sentinel)
4. [Repository Structure](#4-repository-structure)
5. [Installation & Setup](#5-installation--setup)
6. [Interactive CLI & Execution Guide](#6-interactive-cli--execution-guide)
7. [Automated Test Suite (41 Test Cases)](#7-automated-test-suite-41-test-cases)
8. [Cross-Domain Enterprise Reusability](#8-cross-domain-enterprise-reusability)

---

## 1. System Architecture

```
+-----------------------------------------------------------------------------------------+
|                                    DATABASE SENTINEL                                     |
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|   +-----------------------+     +-----------------------+     +---------------------+   |
|   |  Dataset Reconciler   |     |  Self-Healing Engine  |     |  Security Sentinel  |   |
|   | &bull; Drift Sync             |     | &bull; Ledger Balance Repair  |     | &bull; SQLi Interception    |   |
|   | &bull; Orphan FK Quarantine   |     | &bull; Missing Index Synthesis|     | &bull; Anomaly Threat Guard |   |
|   | &bull; Parity Verification    |     | &bull; Negative Value Clamp   |     | &bull; Incident Registry    |   |
|   +-----------+-----------+     +-----------+-----------+     +----------+----------+   |
|               |                             |                            |              |
|               +----------------------+      |      +---------------------+              |
|                                      v      v      v                                    |
|   +---------------------------------------------------------------------------------+   |
|   |                        SYSTEM CATALOG & AUDIT METADATA                          |   |
|   |          _system_actions_log  |  _quarantine_records  |  _security_incidents        |   |
|   +----------------------------------+----------------------------------------------+   |
|                                      |                                                  |
|                                      v                                                  |
|   +---------------------------------------------------------------------------------+   |
|   |                        RELATIONAL STORAGE & DOMAIN ENTITIES                     |   |
|   |             customers  |  accounts  |  orders  |  transactions  |  ...              |   |
|   +----------------------------------+----------------------------------------------+   |
|                                      |                                                  |
|                                      v                                                  |
|   +---------------------------------------------------------------------------------+   |
|   |                        SYSTEM REPORTER & HEALTH DASHBOARD                       |   |
|   |         Health Score (0-100)  |  Storage Metrics  |  Executive Markdown Export  |   |
|   +---------------------------------------------------------------------------------+   |
|                                                                                         |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Core Capabilities

### 2.1 Autonomous Dataset Reconciliation
* **Field-Level Drift Synchronization**: Reconciles incoming datasets against primary tables, updating modified columns while preserving unmodified attributes and logging detailed diffs.
* **Orphan Foreign Key Quarantine**: Detects incoming child rows referencing non-existent parent records and isolates them into `_quarantine_records` to preserve referential integrity.
* **Idempotent Ingestion**: Repeated reconciliation of identical datasets produces zero duplicate rows and zero transaction side-effects ($f(f(x)) = f(x)$).
* **Cryptographic Parity Auditing**: Computes record-level checksums between primary relations and external datasets to measure exact parity percentages.

### 2.2 Self-Healing Bug & Flaw Remediation
* **Ledger Balance Auto-Repair**: Cross-checks stored account balances against the calculated sum of transaction records; automatically identifies balance drift and writes compensating adjustments.
* **Automatic Performance Index Synthesis**: Scans foreign keys and join columns for missing indexes, generating and executing `CREATE INDEX` statements to eliminate linear table scans (`SCAN`).
* **Negative Value Remediation**: Detects illegal negative numbers in monetary, balance, or inventory fields, automatically clamping or quarantining corrupt records.
* **Dangling Foreign Key Resolution**: Scans existing relations for child records whose parents were deleted, quarantining them and restoring 100% referential integrity.

### 2.3 Security Sentinel & Suspicious Activity Detection
* **Real-Time SQL Injection (SQLi) Defense**: Inspects incoming queries and inputs for attack signatures:
  * Boolean tautologies (`' OR 1=1 --`, `' OR '1'='1`)
  * Union-based data extraction (`UNION SELECT ...`)
  * Stacked destructive commands (`; DROP TABLE`, `; TRUNCATE`)
  * Command execution attempts (`xp_cmdshell`, `EXEC(`)
  * Time-based blind injection (`WAITFOR DELAY`, `SLEEP(`)
* **Mutation Anomaly Detection**: Intercepts unconstrained mass-deletion attempts attempting to wipe out significant portions of active tables.
* **Persistent Incident Registry**: Records all intercepted threats into `_security_incidents` with timestamps, actor profiles, threat types, and severity levels.

### 2.4 Automated Action Logging & Comprehensive Overview
* **Immutable Action Log**: Every self-healing, reconciliation, or quarantine action is logged into `_system_actions_log` with before and after state snapshots.
* **System Health Score (0–100%)**: Quantitative health evaluation based on unresolved quarantine records, open security incidents, missing indexes, and ledger discrepancies.
* **Automated Reporting**: Generates ASCII terminal dashboards, structured JSON telemetry, and executive Markdown health reports.

---

## 3. The Technology Behind Database Sentinel

* **Python DB-API (PEP 249) Integration**: Built entirely on standard library modules (`sqlite3`, `csv`, `json`, `re`, `hashlib`) with zero third-party dependencies.
* **ACID Transaction Boundaries & WAL Mode**: Enforces `PRAGMA foreign_keys = ON;`, `PRAGMA journal_mode = WAL;`, and atomic transaction commits (`BEGIN TRANSACTION` / `COMMIT` / `ROLLBACK`).
* **Abstract Syntax Tree (AST) Threat Protection**: Neutralizes injection exploits by decoupling SQL instructions from user-supplied parameters.
* **Catalog Introspection**: Leverages SQLite's `sqlite_master` and `PRAGMA table_info / foreign_key_list / index_list` to perform dynamic, domain-agnostic schema analysis.

---

## 4. Repository Structure

```
database_sentinel/
├── sentinel/
│   ├── __init__.py           # Package exports
│   ├── engine.py             # Database engine & catalog introspection
│   ├── reconciler.py         # Dataset reconciler, drift sync & parity engine
│   ├── healer.py             # Self-healing engine (balances, indexes, negatives)
│   ├── security.py           # Threat guard (SQLi detection & anomaly monitor)
│   └── reporter.py           # Action audit logger & health report exporter
├── data/
│   ├── seed_demo.sql         # Multi-table enterprise relational schema & seeds
│   ├── sample_incoming_customers.csv # Incoming sync data with drift & faults
│   └── sample_incoming_orders.csv    # Incoming orders with orphan foreign keys
├── tests/
│   ├── test_engine.py        # 5 tests: Engine & catalog introspection
│   ├── test_reconciler.py    # 5 tests: Reconciliation, drift, and parity
│   ├── test_healer.py        # 5 tests: Self-healing, balance repairs & indexing
│   ├── test_security.py      # 5 tests: SQLi defense & incident logging
│   ├── test_reporter.py      # 3 tests: Health score & dashboard rendering
│   ├── test_cli.py           # 7 tests: CLI administrative commands
│   └── test_comprehensive.py # 11 tests: End-to-end integration workflows
├── sentinel.py               # Unified administrative CLI interface
├── requirements.txt          # Standard library zero-dependency specification
├── .env.example              # Configuration template
├── .gitignore                # Production ignore rules
└── LICENSE                   # MIT Copyright notice
```

---

## 5. Installation & Setup

```bash
# 1. Clone repository
git clone https://github.com/0xlazorr/database-sentinel.git
cd database-sentinel

# 2. Make CLI executable
chmod +x sentinel.py

# 3. Configure environment (optional)
cp .env.example .env
```

---

## 6. Interactive CLI & Execution Guide

### 6.1 Initialize & Seed Database
```bash
python3 sentinel.py init --seed
```

### 6.2 Display System State Overview & Health Score
```bash
python3 sentinel.py status
```
*Expected Console Output:*
```
==============================================================================
                   DATABASE SENTINEL: SYSTEM STATE OVERVIEW
==============================================================================
Database Target : sentinel_store.db (28.0 KB)
Health Score    : 85/100 [WARNING]
Threat Level    : NORMAL (GREEN)
------------------------------------------------------------------------------
RELATIONAL STORAGE INVENTORY:
  User Tables   : 4 tables
  Total Records : 11 rows
  Total Indexes : 0 indexes
    • accounts             3 rows | 0 indexes
    • customers            3 rows | 0 indexes
    • orders               2 rows | 0 indexes
    • transactions         3 rows | 0 indexes
------------------------------------------------------------------------------
AUTONOMOUS ACTIONS & REMEDIATION LOG:
  Total Logged  : 0 actions executed
------------------------------------------------------------------------------
QUARANTINE & RELATIONAL INTEGRITY:
  Quarantined   : 0 corrupted/orphan records isolated
------------------------------------------------------------------------------
SECURITY SENTINEL & ANOMALY DETECTION:
  Incidents     : 0 threats intercepted
==============================================================================
```

### 6.3 Run Autonomous Self-Healing Cycle
```bash
python3 sentinel.py heal
```
*Expected Console Output:*
```
=================================================================
AUTONOMOUS SELF-HEALING CYCLE COMPLETE
=================================================================
Status                    : HEALTH_RESTORED
Total Flaws Remediated    : 4
Performance Indexes Added : 3 ['idx_accounts_customer_id', 'idx_transactions_account_id', 'idx_orders_customer_id']
Dangling FKs Healed       : 0
Illegal Negatives Cleared : 1
Ledger Balances Repaired  : 1
=================================================================
```

### 6.4 Reconcile External Dataset
```bash
python3 sentinel.py reconcile --source data/sample_incoming_customers.csv --table customers --key customer_code
```
*Expected Console Output:*
```
=================================================================
DATASET RECONCILIATION SUMMARY
=================================================================
Total Processed       : 5
New Records Inserted  : 2
Drift State Updated   : 1
Identical Duplicates  : 1
Quarantined Orphans   : 0
Quarantined Corrupt   : 1
Actions Audit Logged  : 4
=================================================================
```

### 6.5 Run Security Threat Inspection
```bash
# Scan malicious SQL injection payload
python3 sentinel.py security-audit --payload "admin' OR 1=1 --"

# View security threat registry
python3 sentinel.py security-audit
```

### 6.6 Export Comprehensive Executive Health Report
```bash
python3 sentinel.py report --output reports/system_health_report.md
```

### 6.7 Run Continuous Autonomous Watchdog Daemon
```bash
python3 sentinel.py daemon --interval 15
```

---

## 7. Automated Test Suite (41 Test Cases)

```bash
python3 -m unittest discover tests
```

```
.........................................
----------------------------------------------------------------------
Ran 41 tests in 3.503s

OK
```

| Test Suite | Test Count | Scope |
| :--- | :---: | :--- |
| **Engine & Catalog Introspection** | 5 Tests | Catalog tables, schema introspection, actions, quarantine |
| **Dataset Reconciliation** | 5 Tests | Inserts, drift sync, orphan quarantine, CSV input, parity scoring |
| **Autonomous Self-Healing** | 5 Tests | Flaw diagnosis, missing index synthesis, ledger repair, negative clamping |
| **Security Sentinel** | 5 Tests | SQLi interception (boolean, union, stacked), benign queries, threat levels |
| **System Reporter** | 3 Tests | Health score calculation, ASCII dashboard, markdown export |
| **Administrative CLI** | 7 Tests | CLI commands (`init`, `status`, `heal`, `reconcile`, `security`, `report`) |
| **End-to-End Integration** | 11 Tests | Full integration workflows, anomaly detection, idempotency, audit trails |
| **Total Test Cases** | **41 Tests** | **100% Passing** |

---

## 8. Cross-Domain Enterprise Reusability

Database Sentinel is completely schema- and domain-agnostic:
* **E-Commerce & Retail**: Reconciles incoming supplier feeds, auto-repairs negative stock levels, auto-indexes order join columns.
* **Financial Services & Banking**: Resolves ledger balance drift between transaction logs and account balances with compensating entries.
* **Healthcare & EHR**: Quarantines malformed patient records while preserving primary table referential integrity.
* **SaaS Telemetry & Events**: Ingests high-frequency event streams, isolates corrupted payloads, and blocks malicious injection attacks.
