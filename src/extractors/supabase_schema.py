import re
import sys
from pathlib import Path
from typing import Dict, Set

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.db import get_connection, execute_write
from src.db_ops import upsert_node, upsert_edge
from src.extractors.constants_scanner import scan_constants

DEFAULT_REPO_ROOT = Path(r"C:\Users\Admin\Desktop\projects\Present-Career-os")

def link_database_schemas(repo_root: Path = DEFAULT_REPO_ROOT):
    conn = get_connection()
    tables: Dict[str, str] = {} # table_name -> node_id

    # 1. Discover all tables from SQL migrations and Prisma schema
    table_pattern = re.compile(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["`\']?([a-zA-Z0-9_]+)["`\']?', re.IGNORECASE)
    prisma_pattern = re.compile(r'model\s+([a-zA-Z0-9_]+)\s*\{', re.MULTILINE)

    migration_dir = repo_root / "supabase" / "migrations"
    if migration_dir.exists():
        for sql_file in migration_dir.glob("*.sql"):
            try:
                content = sql_file.read_text(encoding="utf-8", errors="ignore")
                for m in table_pattern.finditer(content):
                    t_name = m.group(1).lower()
                    if t_name not in tables:
                        tables[t_name] = f"table:{t_name}"
            except Exception:
                pass

    prisma_file = repo_root / "prisma" / "schema.prisma"
    if prisma_file.exists():
        try:
            content = prisma_file.read_text(encoding="utf-8", errors="ignore")
            for m in prisma_pattern.finditer(content):
                m_name = m.group(1).lower()
                if m_name not in tables:
                    tables[m_name] = f"table:{m_name}"
        except Exception:
            pass

    print(f"[1/3] Discovered {len(tables)} unique database tables/models.")
    with execute_write(conn):
        for t_name, node_id in tables.items():
            upsert_node(conn, {
                "id": node_id,
                "name": t_name,
                "kind": "table",
                "filepath": "supabase/migrations",
                "metadata": {"type": "postgresql_table"}
            })

    # 2. Pass 1 Constants
    constants = scan_constants(repo_root)

    # 3. Match queries in API routes and services
    # e.g. .from('campus_exam_results') or prisma.user.findMany
    from_pattern = re.compile(r'\.from\s*\(\s*([\'"`][a-zA-Z0-9_]+[\'"`]|[A-Za-z0-9_.]+)\s*\)')
    prisma_query_pattern = re.compile(r'prisma\.([a-zA-Z0-9_]+)\.')

    search_dirs = [
        repo_root / "src" / "app" / "api",
        repo_root / "src" / "lib" / "services",
        repo_root / "src" / "lib" / "server"
    ]

    edges_created = 0
    scanned_files = 0

    print(f"[2/3] Scanning backend routes & services for database queries...")
    with execute_write(conn):
        for sdir in search_dirs:
            if not sdir.exists():
                continue
            for code_file in sdir.glob("**/*.[tj]s*"):
                scanned_files += 1
                try:
                    content = code_file.read_text(encoding="utf-8", errors="ignore")
                    rel_path = code_file.relative_to(repo_root).as_posix()
                    caller_id = f"file:{rel_path}"

                    # Ensure caller node exists
                    upsert_node(conn, {
                        "id": caller_id,
                        "name": code_file.name,
                        "kind": "file",
                        "filepath": rel_path
                    })

                    # Supabase .from('...')
                    for m in from_pattern.finditer(content):
                        raw_table = m.group(1).strip('\'"`')
                        resolved_table = None

                        if raw_table.lower() in tables:
                            resolved_table = raw_table.lower()
                        elif raw_table in constants:
                            const_val = constants[raw_table].lower()
                            if const_val in tables:
                                resolved_table = const_val

                        if resolved_table:
                            target_id = tables[resolved_table]
                            upsert_edge(conn, {
                                "source_id": caller_id,
                                "target_id": target_id,
                                "kind": "QUERIES",
                                "weight": 2.5
                            })
                            edges_created += 1

                    # Prisma queries: prisma.user.findMany
                    for m in prisma_query_pattern.finditer(content):
                        p_table = m.group(1).lower()
                        if p_table in tables:
                            target_id = tables[p_table]
                            upsert_edge(conn, {
                                "source_id": caller_id,
                                "target_id": target_id,
                                "kind": "QUERIES",
                                "weight": 2.5
                            })
                            edges_created += 1
                except Exception:
                    pass

    conn.close()
    print(f"[3/3] Successfully linked {edges_created} database query edges across {scanned_files} backend files.")
    assert len(tables) > 0, "No tables discovered!"
    return len(tables), edges_created

if __name__ == "__main__":
    t_count, e_count = link_database_schemas()
    print(f"[PASS] Task 2.3 Supabase & Prisma Linker Complete: {t_count} tables, {e_count} query edges.")
