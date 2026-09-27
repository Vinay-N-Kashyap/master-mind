import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.db import get_connection, execute_write
from src.db_ops import upsert_agent, upsert_task

DEFAULT_TASKS_CSV = Path(r"C:\Users\Admin\Desktop\projects\memory of agent\agent_tasks.csv")
DEFAULT_CONTROL_CSV = Path(r"C:\Users\Admin\Desktop\projects\memory of agent\multi_agent_control.csv")

def sync_tasks_and_agents(tasks_csv: Path = DEFAULT_TASKS_CSV, control_csv: Path = DEFAULT_CONTROL_CSV):
    conn = get_connection()
    tasks_count = 0
    agents_count = 0

    # 1. Sync Multi-Agent Control Registry
    if control_csv.exists():
        print(f"[1/2] Reading multi-agent control registry from {control_csv.name}...")
        with open(control_csv, mode="r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            with execute_write(conn):
                for row in reader:
                    agent_name = row.get("Assigned_Agent", "").strip()
                    if not agent_name or agent_name == "None":
                        continue
                    agent_id = agent_name.lower().replace(" ", "-").replace("(", "").replace(")", "").replace("/", "-")
                    upsert_agent(conn, {
                        "agent_id": agent_id,
                        "display_name": agent_name,
                        "active_branch": row.get("Git_Branch"),
                        "worktree_path": row.get("Worktree_Folder")
                    })
                    agents_count += 1
        print(f"      Synced {agents_count} agent branch records.")

    # 2. Sync Agent Tasks Ledger
    if tasks_csv.exists():
        print(f"[2/2] Reading tasks ledger from {tasks_csv.name}...")
        with open(tasks_csv, mode="r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            with execute_write(conn):
                for row in reader:
                    task_id = row.get("Task_ID", "").strip()
                    if not task_id:
                        continue
                    
                    raw_engine = row.get("Execution_Engine", "Antigravity").strip()
                    agent_id = raw_engine.lower().replace(" ", "-").replace("(", "").replace(")", "").replace("/", "-")
                    
                    status = row.get("Status", "IN_PROGRESS").strip().upper()
                    goal = row.get("User_Goal", "").strip()
                    resolution = row.get("Agent_Resolution", "").strip()

                    # Extract problem / solution gracefully from resolution
                    problem = goal
                    solution = resolution[:500] if resolution else "Task resolution in progress."
                    
                    date_val = row.get("Date", "").strip()
                    time_val = row.get("Time", "").strip()
                    created_at = f"{date_val} {time_val}" if date_val and time_val else None

                    completion = 100.0 if status == "COMPLETED" else 50.0

                    upsert_task(conn, {
                        "task_id": task_id,
                        "agent_id": agent_id,
                        "agent_name": raw_engine,
                        "title": goal[:120] if goal else task_id,
                        "problem_statement": problem,
                        "root_cause": "Operational request / issue report",
                        "solution_summary": solution,
                        "git_branch": "main",
                        "status": status,
                        "completion_percentage": completion,
                        "created_at": created_at,
                        "completed_at": created_at if status == "COMPLETED" else None
                    })
                    tasks_count += 1
        print(f"      Synced {tasks_count} tasks into SQLite.")

    # Verification
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tasks;")
    total_tasks = cur.fetchone()[0]
    conn.close()

    print(f"[SUCCESS] Task Ledger Sync complete: {total_tasks} tasks recorded.")
    assert total_tasks > 0, "No tasks were ingested!"
    return total_tasks

if __name__ == "__main__":
    t = sync_tasks_and_agents()
    print(f"[PASS] Task 3.1 Task Ledger Sync Succeeded with Exit Code 0 ({t} tasks).")
