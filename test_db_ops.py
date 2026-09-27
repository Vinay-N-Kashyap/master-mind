import threading
import sqlite3
from src.db import get_connection, execute_write
from src.db_ops import upsert_node, upsert_edge, upsert_task, link_task_to_node

def run_tests():
    conn = get_connection()
    
    # 1. Test Single & Batch Node Upserts
    with execute_write(conn):
        for i in range(10):
            upsert_node(conn, {
                "id": f"node_{i}",
                "name": f"Function_{i}",
                "kind": "function",
                "filepath": f"src/module_{i}.ts",
                "line_start": 1,
                "line_end": 25,
                "community_id": 1,
                "metadata": {"export": True}
            })
    
    # Verify count
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM nodes WHERE id LIKE 'node_%';")
    count = cur.fetchone()[0]
    assert count == 10, f"Expected 10 nodes, got {count}"
    print(f"[PASS] 10 mock nodes inserted.")

    # 2. Test Edge Upserts
    with execute_write(conn):
        for i in range(5):
            upsert_edge(conn, {
                "source_id": f"node_{i}",
                "target_id": f"node_{i+1}",
                "kind": "CALLS",
                "weight": 1.0
            })
    
    cur.execute("SELECT COUNT(*) FROM edges WHERE source_id LIKE 'node_%';")
    edge_count = cur.fetchone()[0]
    assert edge_count == 5, f"Expected 5 edges, got {edge_count}"
    print(f"[PASS] 5 mock edges inserted.")

    # 3. Test Node Update (Idempotency)
    with execute_write(conn):
        upsert_node(conn, {
            "id": "node_0",
            "name": "Updated_Function_0",
            "kind": "function",
            "filepath": "src/module_0.ts",
            "line_start": 1,
            "line_end": 50,
            "community_id": 2,
            "metadata": {"updated": True}
        })
    
    cur.execute("SELECT name, community_id FROM nodes WHERE id = 'node_0';")
    name, comm_id = cur.fetchone()
    assert name == "Updated_Function_0" and comm_id == 2, "Node update failed"
    print(f"[PASS] Node idempotency & update verified.")

    # 4. Test Task & Socio-Technical Linking
    with execute_write(conn):
        upsert_task(conn, {
            "task_id": "TASK-TEST-001",
            "agent_id": "claude-cli",
            "title": "Fix Payroll Race Condition",
            "problem_statement": "Double clicks execute payroll twice",
            "root_cause": "Missing server lock",
            "solution_summary": "Atomic period_key reservation with rollback",
            "git_branch": "claude/audit-fixes",
            "commit_sha": "e2441516",
            "status": "COMPLETED",
            "completion_percentage": 100.0
        })
        link_task_to_node(conn, "TASK-TEST-001", "node_0", "MODIFIED")
    
    cur.execute("SELECT COUNT(*) FROM task_touched_nodes WHERE task_id = 'TASK-TEST-001';")
    touched_count = cur.fetchone()[0]
    assert touched_count == 1, "Task-to-node linking failed"
    print(f"[PASS] Task and socio-technical code linking verified.")

    # 5. Concurrency Stress Test: 2 Threads Writing with BEGIN IMMEDIATE
    errors = []
    def worker(worker_id):
        try:
            worker_conn = get_connection()
            with execute_write(worker_conn):
                upsert_node(worker_conn, {
                    "id": f"concurrent_node_{worker_id}",
                    "name": f"Concurrent_{worker_id}",
                    "kind": "class",
                    "filepath": f"src/worker_{worker_id}.ts"
                })
            worker_conn.close()
        except Exception as e:
            errors.append((worker_id, str(e)))

    t1 = threading.Thread(target=worker, args=(1,))
    t2 = threading.Thread(target=worker, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(errors) == 0, f"Concurrency deadlocks encountered: {errors}"
    print(f"[PASS] Multi-threaded concurrent write test passed with 0 deadlocks.")

    # Clean up test nodes
    with execute_write(conn):
        conn.execute("DELETE FROM task_touched_nodes WHERE task_id = 'TASK-TEST-001';")
        conn.execute("DELETE FROM tasks WHERE task_id = 'TASK-TEST-001';")
        conn.execute("DELETE FROM edges WHERE source_id LIKE 'node_%';")
        conn.execute("DELETE FROM nodes WHERE id LIKE 'node_%' OR id LIKE 'concurrent_node_%';")
    
    conn.close()
    print("[ALL TESTS PASSED] Task 1.2 Deterministic Verification Succeeded with Exit Code 0.")

if __name__ == "__main__":
    run_tests()
