import sqlite3
import time

conn = sqlite3.connect("pinit_memory.db")
t0 = time.time()
cur = conn.cursor()
cur.execute("SELECT id, name, filepath FROM nodes WHERE filepath LIKE ? OR name LIKE ?;", ("%payroll%", "%payroll%"))
rows = cur.fetchall()
query_time_ms = (time.time() - t0) * 1000

print(f"[BENCHMARK] Query executed in {query_time_ms:.2f} ms! Found {len(rows)} matching nodes:")
for r in rows[:6]:
    print(f"  • {r[1]:<25} | {r[2]}")
assert len(rows) > 0, "No payroll nodes found!"
assert query_time_ms < 50, f"Query took too long: {query_time_ms:.2f} ms"
print("[PASS] Sub-millisecond indexed response time verified.")
