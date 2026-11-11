-- Enterprise Demonstration Relational Schema
PRAGMA foreign_keys = ON;

-- 1. Customers Table
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_code TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'STANDARD',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 2. Accounts Table (Financial Ledgers)
CREATE TABLE IF NOT EXISTS accounts (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    account_number TEXT NOT NULL UNIQUE,
    balance NUMERIC NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
);

-- 3. Transactions Table (Double-Entry Audit Stream)
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    amount NUMERIC NOT NULL,
    tx_type TEXT NOT NULL,
    reference TEXT NOT NULL UNIQUE,
    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 4. Orders Table
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id) ON DELETE RESTRICT,
    order_code TEXT NOT NULL UNIQUE,
    total_amount NUMERIC NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Baseline Seed Records
INSERT OR IGNORE INTO customers (customer_id, customer_code, full_name, email, tier) VALUES
(1, 'CUST-001', 'Alice Johnson', 'alice@enterprise.com', 'PREMIUM'),
(2, 'CUST-002', 'Bob Smith', 'bob@enterprise.com', 'STANDARD'),
(3, 'CUST-003', 'Carol Danvers', 'carol@enterprise.com', 'ENTERPRISE');

-- Seed Accounts with 1 intentional ledger discrepancy for self-healing demonstration
INSERT OR IGNORE INTO accounts (account_id, customer_id, account_number, balance) VALUES
(1, 1, 'ACC-1001', 5000.0),   -- Clean account
(2, 2, 'ACC-1002', 1200.0),   -- Corrupted balance: actual sum of txs will be 1500.0 (drift)
(3, 3, 'ACC-1003', -250.0);   -- Flaw: illegal negative balance for auto-healing

-- Seed Transactions matching Account 1 and 2
INSERT OR IGNORE INTO transactions (transaction_id, account_id, amount, tx_type, reference) VALUES
(1, 1, 5000.0, 'CREDIT', 'TX-10001'),
(2, 2, 1000.0, 'CREDIT', 'TX-10002'),
(3, 2, 500.0, 'CREDIT', 'TX-10003');  -- Sum is 1500.0, but stored balance is 1200.0

-- Seed Orders
INSERT OR IGNORE INTO orders (order_id, customer_id, order_code, total_amount, status) VALUES
(1, 1, 'ORD-501', 350.0, 'COMPLETED'),
(2, 2, 'ORD-502', 120.0, 'PROCESSING');
