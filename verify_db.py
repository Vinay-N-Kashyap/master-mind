import sqlite3
from pathlib import Path

db_path = Path("pinit_memory.db")
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cur.fetchall()]
print(f"VERIFIED TABLES ({len(tables)}):", tables)

cur.execute("PRAGMA journal_mode;")
journal = cur.fetchone()[0]
print("JOURNAL MODE:", journal)

expected_tables = ["nodes", "edges", "communities", "agents", "tasks", "task_touched_nodes", "test_verifications"]
for t in expected_tables:
    assert t in tables, f"Missing table: {t}"

assert journal == "wal", f"Expected WAL mode, got {journal}"
print("[PASS] 100% of required tables exist and WAL mode is active.")
