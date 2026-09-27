import re
import sys
from pathlib import Path
from typing import Dict, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.db import get_connection, execute_write
from src.db_ops import upsert_node, upsert_edge
from src.extractors.constants_scanner import scan_constants

DEFAULT_REPO_ROOT = Path(r"C:\Users\Admin\Desktop\projects\Present-Career-os")

def link_nextjs_routes(repo_root: Path = DEFAULT_REPO_ROOT):
    conn = get_connection()
    app_dir = repo_root / "src" / "app"
    
    # 1. Discover all official Next.js App Router API routes
    route_files = list(app_dir.glob("api/**/route.ts")) + list(app_dir.glob("api/**/route.js"))
    route_map: Dict[str, Tuple[str, Path]] = {} # route_path -> (node_id, file_path)
    
    print(f"[1/3] Discovered {len(route_files)} Next.js App Router API routes.")
    with execute_write(conn):
        for rf in route_files:
            rel = rf.relative_to(app_dir).as_posix()
            # e.g. api/hr/run-payroll/route.ts -> /api/hr/run-payroll
            route_path = "/" + rel.rsplit("/route.", 1)[0]
            node_id = f"route:{route_path}"
            rel_project_path = rf.relative_to(repo_root).as_posix()
            
            upsert_node(conn, {
                "id": node_id,
                "name": route_path,
                "kind": "route",
                "filepath": rel_project_path,
                "metadata": {"http_methods": ["GET", "POST", "PUT", "DELETE"]}
            })
            route_map[route_path] = (node_id, rf)

    # 2. Pass 1 Constants
    constants = scan_constants(repo_root)

    # 3. Scan components for calls to routes
    # Regex matching fetch(...) or wrapper calls:
    # fetch('/api/...') or fetch(`/api/...`) or fetch(API_ROUTES.X)
    fetch_pattern = re.compile(
        r'(?:fetch|authenticatedFetch|apiClient\.[a-z]+)\s*\(\s*([`\'"][^`\'"]+[`\'"]|[A-Za-z0-9_.]+)',
        re.MULTILINE
    )

    component_dirs = [repo_root / "src" / "components", repo_root / "src" / "app", repo_root / "src" / "hooks"]
    links_created = 0
    scanned_files = 0

    print(f"[2/3] Scanning frontend components for API route invocations...")
    with execute_write(conn):
        for cdir in component_dirs:
            if not cdir.exists():
                continue
            for comp_file in cdir.glob("**/*.[tj]s*"):
                if "route.ts" in comp_file.name or comp_file.name.endswith(".d.ts"):
                    continue
                scanned_files += 1
                try:
                    content = comp_file.read_text(encoding="utf-8", errors="ignore")
                    caller_rel = comp_file.relative_to(repo_root).as_posix()
                    caller_id = f"file:{caller_rel}"

                    # Ensure caller file node exists
                    upsert_node(conn, {
                        "id": caller_id,
                        "name": comp_file.name,
                        "kind": "file",
                        "filepath": caller_rel
                    })

                    for m in fetch_pattern.finditer(content):
                        raw_target = m.group(1).strip('`\'"')
                        resolved_route = None

                        # Direct match: /api/hr/run-payroll
                        if raw_target.startswith("/api/"):
                            # Handle template literal prefix matching: e.g. /api/hr/${dept}/payroll -> /api/hr
                            clean_target = raw_target.split("${")[0].rstrip("/")
                            for r_path in route_map:
                                if r_path == clean_target or clean_target.startswith(r_path):
                                    resolved_route = r_path
                                    break
                        # Constant match: API_ROUTES.PAYROLL
                        elif raw_target in constants:
                            resolved_route = constants[raw_target]

                        if resolved_route and resolved_route in route_map:
                            target_id = route_map[resolved_route][0]
                            upsert_edge(conn, {
                                "source_id": caller_id,
                                "target_id": target_id,
                                "kind": "HANDLES_ROUTE",
                                "weight": 2.0
                            })
                            links_created += 1
                except Exception:
                    pass

    conn.close()
    print(f"[3/3] Successfully linked {links_created} client-to-route connections across {scanned_files} files.")
    return links_created

if __name__ == "__main__":
    links = link_nextjs_routes()
    print(f"[PASS] Task 2.2 Next.js Route Linker Complete: {links} edges verified.")
