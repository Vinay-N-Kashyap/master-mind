import subprocess
import sys
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.db import get_connection, execute_write
from src.db_ops import upsert_task, link_task_to_node, upsert_node

DEFAULT_REPO_ROOT = Path(r"C:\Users\Admin\Desktop\projects\Present-Career-os")

def harvest_git_commits(repo_root: Path = DEFAULT_REPO_ROOT, max_commits: int = 50):
    conn = get_connection()

    # 1. Fetch recent git commits
    log_cmd = [
        "git", "-C", str(repo_root),
        "log", f"-n{max_commits}",
        "--format=%H|%an|%ae|%ad|%s"
    ]
    res = subprocess.run(log_cmd, capture_output=True, text=True, check=True)
    lines = [line.strip() for line in res.stdout.strip().split("\n") if line.strip()]

    print(f"[1/2] Harvesting last {len(lines)} git commits from {repo_root.name}...")
    
    harvested = 0
    links_created = 0

    with execute_write(conn):
        for line in lines:
            parts = line.split("|", 4)
            if len(parts) < 5:
                continue
            sha, author, email, date_str, subject = parts
            short_sha = sha[:8]

            # Determine agent
            agent_id = "human-developer"
            author_lower = author.lower()
            if "claude" in author_lower or "claude" in subject.lower():
                agent_id = "claude-cli"
            elif "antigravity" in author_lower or "gemini" in author_lower:
                agent_id = "antigravity-ide"

            task_id = f"COMMIT-{short_sha}"

            # Get touched files
            diff_cmd = [
                "git", "-C", str(repo_root),
                "diff-tree", "--no-commit-id", "--name-only", "-r", sha
            ]
            diff_res = subprocess.run(diff_cmd, capture_output=True, text=True)
            touched_files = [f.strip() for f in diff_res.stdout.strip().split("\n") if f.strip()]

            # Record task in SQLite
            upsert_task(conn, {
                "task_id": task_id,
                "agent_id": agent_id,
                "agent_name": author,
                "title": subject[:120],
                "problem_statement": subject,
                "root_cause": "Git commit delivery",
                "solution_summary": f"Modified {len(touched_files)} files: {', '.join(touched_files[:5])}",
                "git_branch": "main",
                "commit_sha": sha,
                "status": "COMPLETED",
                "completion_percentage": 100.0,
                "created_at": date_str,
                "completed_at": date_str
            })
            harvested += 1

            # Link task to file nodes
            for tf in touched_files:
                file_node_id = f"file:{tf}"
                # Ensure file node exists
                upsert_node(conn, {
                    "id": file_node_id,
                    "name": Path(tf).name,
                    "kind": "file",
                    "filepath": tf
                })
                link_task_to_node(conn, task_id, file_node_id, "MODIFIED")
                links_created += 1

    conn.close()
    print(f"[2/2] Ingested {harvested} commits and linked {links_created} file relationships.")
    return harvested, links_created

def verify_specific_commit(short_sha: str = "e2441516"):
    """Deterministic Verification Test for specific commit."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.task_id, t.agent_id, t.title, n.filepath
        FROM tasks t
        JOIN task_touched_nodes tn ON t.task_id = tn.task_id
        JOIN nodes n ON tn.node_id = n.id
        WHERE t.commit_sha LIKE ?;
    """, (f"{short_sha}%",))
    rows = cur.fetchall()
    conn.close()
    
    print(f"\n[VERIFICATION CHECK] Commit {short_sha} mapped to {len(rows)} files:")
    for r in rows:
        print(f"  • Task: {r[0]} | Agent: {r[1]} | File: {r[3]}")
    
    assert len(rows) > 0, f"Commit {short_sha} was not harvested or linked to files!"
    print(f"[PASS] Commit {short_sha} socio-technical link verified!")

if __name__ == "__main__":
    harvest_git_commits()
    verify_specific_commit("e2441516")
    print("[PASS] Task 3.2 Git Commit Harvester Succeeded with Exit Code 0.")
