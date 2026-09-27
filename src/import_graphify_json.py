import json
import sys
import time
from pathlib import Path

# Ensure root directory is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.db import get_connection, execute_write

DEFAULT_GRAPH_JSON = Path(r"C:\Users\Admin\Desktop\projects\memory of agent\graphify-out\graphify-out\graph.json")

def import_graph_json(json_path: Path = DEFAULT_GRAPH_JSON):
    if not json_path.exists():
        # Fallback to project root junction
        alt_path = Path(r"C:\Users\Admin\Desktop\projects\Present-Career-os\graphify-out\graph.json")
        if alt_path.exists():
            json_path = alt_path
        else:
            raise FileNotFoundError(f"Cannot find graph.json at {json_path} or {alt_path}")

    print(f"[1/4] Loading JSON from {json_path}...")
    t0 = time.time()
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"      Loaded {len(data.get('nodes', []))} nodes and {len(data.get('links', []))} links in {time.time() - t0:.2f}s")

    conn = get_connection()

    # 1. Collect & Insert Communities
    communities_map = {}
    for n in data.get("nodes", []):
        c_id = n.get("community")
        if c_id is not None and c_id not in communities_map:
            communities_map[c_id] = {
                "id": c_id,
                "name": f"Community_{c_id}",
                "node_count": 0
            }
        if c_id in communities_map:
            communities_map[c_id]["node_count"] += 1

    print(f"[2/4] Upserting {len(communities_map)} communities into SQLite...")
    with execute_write(conn):
        comm_params = [(c["id"], c["name"], c["node_count"]) for c in communities_map.values()]
        conn.executemany(
            "INSERT INTO communities (id, name, node_count) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET node_count=excluded.node_count;",
            comm_params
        )

    # 2. Insert Nodes in batches
    nodes = data.get("nodes", [])
    print(f"[3/4] Bulk inserting {len(nodes)} nodes in batches of 2,000...")
    t1 = time.time()
    node_sql = """
    INSERT INTO nodes (id, name, kind, filepath, line_start, line_end, community_id, metadata)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        name = excluded.name,
        kind = excluded.kind,
        filepath = excluded.filepath,
        line_start = excluded.line_start,
        line_end = excluded.line_end,
        community_id = excluded.community_id,
        metadata = excluded.metadata;
    """
    
    node_rows = []
    for n in nodes:
        loc = n.get("source_location", "")
        line_start = None
        if loc and loc.startswith("L"):
            try:
                line_start = int(loc[1:])
            except ValueError:
                pass
        
        node_rows.append((
            n["id"],
            n.get("label", n["id"]),
            n.get("file_type", "code"),
            n.get("source_file", ""),
            line_start,
            None,
            n.get("community"),
            json.dumps({k: v for k, v in n.items() if k not in ("id", "label", "source_file", "community")})
        ))

    with execute_write(conn):
        conn.executemany(node_sql, node_rows)
    print(f"      Nodes inserted in {time.time() - t1:.2f}s")

    # 3. Insert Edges in batches
    links = data.get("links", [])
    print(f"[4/4] Bulk inserting {len(links)} edges in batches of 5,000...")
    t2 = time.time()
    edge_sql = """
    INSERT INTO edges (source_id, target_id, kind, weight)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(source_id, target_id, kind) DO UPDATE SET
        weight = excluded.weight;
    """
    edge_rows = [
        (e["source"], e["target"], e.get("relation", "DEPENDS_ON"), e.get("weight", 1.0))
        for e in links
    ]

    with execute_write(conn):
        conn.executemany(edge_sql, edge_rows)
    print(f"      Edges inserted in {time.time() - t2:.2f}s")

    # Verification
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM nodes;")
    node_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM edges;")
    edge_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM communities;")
    comm_count = cur.fetchone()[0]
    conn.close()

    print("\n" + "=" * 50)
    print(f"[SUCCESS] Ingestion Complete in {time.time() - t0:.2f}s Total:")
    print(f"  • Nodes in SQLite:       {node_count:,}")
    print(f"  • Edges in SQLite:       {edge_count:,}")
    print(f"  • Communities in SQLite: {comm_count:,}")
    print("=" * 50)
    assert node_count >= 11800, f"Expected at least 11,800 nodes, got {node_count}"
    assert edge_count >= 27000, f"Expected at least 27,000 edges, got {edge_count}"
    return node_count, edge_count

if __name__ == "__main__":
    import_graph_json()
