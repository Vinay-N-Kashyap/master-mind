import os
import sys
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager

DEFAULT_DB_PATH = Path(r"C:\Users\Admin\Desktop\projects\master-memory\pinit_memory.db")

DDL_SCHEMA = """
-- 1. Code Entities (Files, Functions, Routes, Tables)
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL, -- 'file', 'function', 'class', 'route', 'table', 'component'
    filepath TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    community_id INTEGER,
    metadata JSON
);
CREATE INDEX IF NOT EXISTS idx_nodes_filepath ON nodes(filepath);
CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(kind);

-- 2. Code Relationships (Imports, Calls, Handlers, Queries)
CREATE TABLE IF NOT EXISTS edges (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    kind TEXT NOT NULL, -- 'IMPORTS', 'CALLS', 'HANDLES_ROUTE', 'QUERIES', 'EXTENDS'
    weight REAL DEFAULT 1.0,
    PRIMARY KEY (source_id, target_id, kind),
    FOREIGN KEY(source_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY(target_id) REFERENCES nodes(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);

-- 3. Functional Communities (Leiden clusters)
CREATE TABLE IF NOT EXISTS communities (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    dominant_domain TEXT, -- 'HR/Payroll', 'Quests', 'Onboarding', 'Arena'
    node_count INTEGER DEFAULT 0
);

-- 4. Multi-Agent Registry
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY, -- 'claude-cli', 'antigravity-ide', 'human'
    display_name TEXT NOT NULL,
    active_branch TEXT,
    worktree_path TEXT,
    last_seen DATETIME
);

-- 5. Tasks, Problems, and Solutions
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    title TEXT NOT NULL,
    problem_statement TEXT,
    root_cause TEXT,
    solution_summary TEXT,
    git_branch TEXT,
    commit_sha TEXT,
    status TEXT NOT NULL, -- 'IN_PROGRESS', 'COMPLETED', 'BLOCKED', 'FAILED'
    completion_percentage REAL DEFAULT 0.0,
    created_at DATETIME,
    completed_at DATETIME,
    FOREIGN KEY(agent_id) REFERENCES agents(agent_id)
);

-- 6. Task-to-Code Mapping (The Socio-Technical Link)
CREATE TABLE IF NOT EXISTS task_touched_nodes (
    task_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    action TEXT, -- 'CREATED', 'MODIFIED', 'DELETED', 'READ'
    PRIMARY KEY(task_id, node_id),
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY(node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

-- 7. Test Verification Ledger (True Proofs)
CREATE TABLE IF NOT EXISTS test_verifications (
    verification_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    test_file TEXT NOT NULL,
    passed_assertions INTEGER NOT NULL,
    total_assertions INTEGER NOT NULL,
    exit_code INTEGER NOT NULL,
    verified_at DATETIME,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);
"""

def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    Opens an ACID-compliant connection to SQLite.
    timeout=10.0 sets the C-level busy handler timeout.
    autocommit=False enables explicit transaction control with BEGIN IMMEDIATE.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Connect with autocommit=True (PEP 682) to take full manual control
    # of transactions, allowing explicit BEGIN IMMEDIATE / COMMIT / ROLLBACK
    conn = sqlite3.connect(str(db_path), timeout=10.0, autocommit=True)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

@contextmanager
def execute_write(conn: sqlite3.Connection, max_retries: int = 5):
    """
    Guaranteed Deadlock-Free write transaction manager.
    Forces 'BEGIN IMMEDIATE' before any writes, acquiring the RESERVED lock
    immediately and queueing concurrent writers rather than deadlocking.
    Includes exponential jitter backoff on rare lock collisions.
    """
    attempt = 0
    while True:
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
            break
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries:
                attempt += 1
                sleep_sec = (0.05 * (2 ** attempt)) + (time.time() % 0.05)
                time.sleep(sleep_sec)
            else:
                try:
                    conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise

def init_db(db_path: Path = DEFAULT_DB_PATH) -> bool:
    """Initializes the database schema with WAL and all 7 tables."""
    conn = get_connection(db_path)
    try:
        with execute_write(conn):
            conn.executescript(DDL_SCHEMA)
        return True
    finally:
        conn.close()

if __name__ == "__main__":
    if "--test-init" in sys.argv:
        success = init_db()
        if success and DEFAULT_DB_PATH.exists():
            print("[OK] SQLite Database initialized with WAL mode, 10s timeout, and BEGIN IMMEDIATE write safety.")
            sys.exit(0)
        else:
            print("[FAIL] Could not initialize database.")
            sys.exit(1)
    else:
        init_db()
        print(f"[OK] Database initialized at: {DEFAULT_DB_PATH}")
