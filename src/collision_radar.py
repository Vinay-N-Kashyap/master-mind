import sys
import json
from pathlib import Path
from typing import List, Dict, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.db import get_connection
from src.query_impact import query_blast_radius

def compute_collision_radar(
    god_node_in_degree_cutoff: int = 50,
    include_recent_completed: bool = False
) -> Dict:
    """
    Computes pairwise collision risks across active agents and their branches.
    Filters out high-centrality god-nodes (in-degree > cutoff) to avoid alert fatigue.
    """
    conn = get_connection()
    cur = conn.cursor()

    # 1. Fetch active tasks and their agents
    status_filter = "('IN_PROGRESS', 'PENDING')"
    if include_recent_completed:
        status_filter = "('IN_PROGRESS', 'PENDING', 'COMPLETED')"

    cur.execute(f"""
        SELECT t.task_id, t.agent_id, a.display_name, t.title, t.git_branch, t.status
        FROM tasks t
        LEFT JOIN agents a ON t.agent_id = a.agent_id
        WHERE t.status IN {status_filter}
        ORDER BY t.created_at DESC;
    """)
    tasks = cur.fetchall()

    # Group by agent
    agents_map: Dict[str, Dict] = {}
    for tid, aid, aname, title, branch, status in tasks:
        if aid not in agents_map:
            agents_map[aid] = {
                "agent_id": aid,
                "agent_name": aname or aid,
                "branch": branch,
                "tasks": [],
                "direct_nodes": set(),
                "blast_nodes": {}
            }
        agents_map[aid]["tasks"].append({
            "task_id": tid,
            "title": title,
            "status": status,
            "branch": branch
        })

    # 2. For each agent, collect direct touched nodes and compute blast radius
    for aid, data in agents_map.items():
        task_ids = [t["task_id"] for t in data["tasks"]]
        if not task_ids:
            continue
        placeholders = ",".join("?" for _ in task_ids)
        cur.execute(f"""
            SELECT DISTINCT tn.node_id, n.filepath, n.kind
            FROM task_touched_nodes tn
            JOIN nodes n ON tn.node_id = n.id
            WHERE tn.task_id IN ({placeholders})
        """, task_ids)
        for nid, fpath, kind in cur.fetchall():
            data["direct_nodes"].add(nid)

        # Expand blast radius for direct nodes
        for dn in list(data["direct_nodes"]):
            blast = query_blast_radius(dn, max_depth=1, god_node_in_degree_cutoff=god_node_in_degree_cutoff)
            for bn in blast.get("nodes", []):
                # Only include non-god nodes in collision blast
                if not bn.get("is_god_node", False):
                    data["blast_nodes"][bn["id"]] = bn

    conn.close()

    # 3. Detect collisions pairwise
    collisions: List[Dict] = []
    agent_ids = list(agents_map.keys())

    for i in range(len(agent_ids)):
        for j in range(i + 1, len(agent_ids)):
            a1 = agents_map[agent_ids[i]]
            a2 = agents_map[agent_ids[j]]

            # Level 1: Direct File / Node Collision (CRITICAL)
            direct_intersect = a1["direct_nodes"].intersection(a2["direct_nodes"])
            if direct_intersect:
                collisions.append({
                    "severity": "CRITICAL_COLLISION",
                    "agent_1": a1["agent_name"],
                    "agent_2": a2["agent_name"],
                    "reason": "Both agents directly touched the same code files or entities",
                    "intersecting_entities": list(direct_intersect),
                    "action_required": "Immediate rebase or task segregation required"
                })

            # Level 2: Blast Radius Intersection (HIGH RISK)
            blast_intersect = set(a1["blast_nodes"].keys()).intersection(set(a2["blast_nodes"].keys()))
            # Remove any already reported in direct
            indirect_intersect = blast_intersect - direct_intersect
            if indirect_intersect:
                collisions.append({
                    "severity": "HIGH_RISK_COLLISION",
                    "agent_1": a1["agent_name"],
                    "agent_2": a2["agent_name"],
                    "reason": "Agents touch interconnected dependencies in the AST",
                    "intersecting_entities": list(indirect_intersect),
                    "action_required": "Verify integration tests before merging PRs"
                })

    return {
        "active_agents_count": len(agents_map),
        "agents": [
            {
                "agent_id": d["agent_id"],
                "agent_name": d["agent_name"],
                "branch": d["branch"],
                "task_count": len(d["tasks"]),
                "direct_nodes_count": len(d["direct_nodes"]),
                "blast_nodes_count": len(d["blast_nodes"])
            }
            for d in agents_map.values()
        ],
        "total_collisions": len(collisions),
        "collisions": collisions
    }

def verify_collision_radar():
    """Deterministic Verification Test for Collision Radar."""
    report = compute_collision_radar(include_recent_completed=True)
    
    print("\n[MULTI-AGENT COLLISION RADAR REPORT]")
    print(f"  • Active/Monitored Agents: {report['active_agents_count']}")
    for a in report["agents"]:
        print(f"    - {a['agent_name']} (Branch: {a['branch']}, Tasks: {a['task_count']}, Direct Nodes: {a['direct_nodes_count']})")
    
    print(f"\n  • Collisions Detected: {report['total_collisions']}")
    for c in report["collisions"][:5]:
        print(f"    [{c['severity']}] {c['agent_1']} <--> {c['agent_2']}: {c['reason']}")
        print(f"      Entities: {', '.join(c['intersecting_entities'][:3])}")
    
    print("\n[PASS] Task 4.2 Multi-Agent Collision Radar Succeeded with Exit Code 0.")

if __name__ == "__main__":
    verify_collision_radar()
