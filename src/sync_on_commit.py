import os
import sys
import time
import subprocess
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

LOCK_FILE = PROJECT_ROOT / ".sync.lock"

def acquire_lock() -> bool:
    """Attempts to acquire atomic PID lock to prevent git rebase stampedes."""
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            # Check if process is still running on Windows
            check_cmd = f"Get-Process -Id {pid} -ErrorAction SilentlyContinue"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", check_cmd], capture_output=True, text=True)
            if res.stdout.strip():
                print(f"[MUTEX] Another sync process (PID {pid}) is already running. Skipping concurrent run.")
                return False
        except Exception:
            pass
        # Stale lock, overwrite
        try:
            LOCK_FILE.unlink()
        except Exception:
            pass

    try:
        LOCK_FILE.write_text(str(os.getpid()))
        return True
    except Exception as e:
        print(f"[MUTEX] Failed to acquire lock: {e}")
        return False

def release_lock():
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except Exception:
        pass

def run_sync_pipeline():
    """Runs the continuous synchronization pipeline."""
    if not acquire_lock():
        return

    print("=" * 60)
    print("[MASTER MEMORY ENGINE] Continuous Sync Initiated")
    print("=" * 60)
    start_time = time.time()

    try:
        # 1. Harvest Git Commits
        from src.git_commit_harvester import harvest_git_commits
        commits, links = harvest_git_commits(max_commits=20)
        print(f"  • Harvested {commits} commits ({links} touched files)")

        # 2. Sync Agent Tasks
        from src.sync_agent_tasks import sync_tasks_and_agents
        synced_tasks = sync_tasks_and_agents()
        print(f"  • Synced {synced_tasks} agent tasks from CSVs")

        # 3. Export Dashboard Data
        from src.export_dashboard_data import export_dashboard_data
        out_file = export_dashboard_data()
        print(f"  • Exported fresh dashboard payload to {out_file.name}")

        elapsed = time.time() - start_time
        print(f"[MASTER MEMORY ENGINE] Sync pipeline completed successfully in {elapsed:.2f}s (Exit 0)")
    except Exception as e:
        print(f"[ERROR] Sync pipeline encountered an error: {e}", file=sys.stderr)
        raise
    finally:
        release_lock()

if __name__ == "__main__":
    run_sync_pipeline()
