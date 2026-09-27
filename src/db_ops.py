import json
import sqlite3
from typing import Dict, Any, List, Optional
from src.db import execute_write, get_connection

def upsert_node(conn: sqlite3.Connection, node: Dict[str, Any]) -> None:
    """Inserts or updates a code entity node."""
    sql = """
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
    metadata_json = json.dumps(node.get("metadata", {})) if isinstance(node.get("metadata"), dict) else node.get("metadata")
    params = (
        node["id"],
        node["name"],
        node["kind"],
        node["filepath"],
        node.get("line_start"),
        node.get("line_end"),
        node.get("community_id"),
        metadata_json
    )
    conn.execute(sql, params)

def upsert_nodes_batch(conn: sqlite3.Connection, nodes: List[Dict[str, Any]]) -> None:
    """Bulk upsert for nodes within an active transaction."""
    sql = """
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
    params_list = [
        (
            n["id"],
            n["name"],
            n["kind"],
            n["filepath"],
            n.get("line_start"),
            n.get("line_end"),
            n.get("community_id"),
            json.dumps(n.get("metadata", {})) if isinstance(n.get("metadata"), dict) else n.get("metadata")
        )
        for n in nodes
    ]
    conn.executemany(sql, params_list)

def upsert_edge(conn: sqlite3.Connection, edge: Dict[str, Any]) -> None:
    """Inserts or updates a dependency/call edge."""
    sql = """
    INSERT INTO edges (source_id, target_id, kind, weight)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(source_id, target_id, kind) DO UPDATE SET
        weight = excluded.weight;
    """
    params = (
        edge["source_id"],
        edge["target_id"],
        edge["kind"],
        edge.get("weight", 1.0)
    )
    conn.execute(sql, params)

def upsert_edges_batch(conn: sqlite3.Connection, edges: List[Dict[str, Any]]) -> None:
    """Bulk upsert for edges within an active transaction."""
    sql = """
    INSERT INTO edges (source_id, target_id, kind, weight)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(source_id, target_id, kind) DO UPDATE SET
        weight = excluded.weight;
    """
    params_list = [
        (e["source_id"], e["target_id"], e["kind"], e.get("weight", 1.0))
        for e in edges
    ]
    conn.executemany(sql, params_list)

def upsert_agent(conn: sqlite3.Connection, agent: Dict[str, Any]) -> None:
    """Registers or updates an active agent."""
    sql = """
    INSERT INTO agents (agent_id, display_name, active_branch, worktree_path, last_seen)
    VALUES (?, ?, ?, ?, datetime('now'))
    ON CONFLICT(agent_id) DO UPDATE SET
        display_name = excluded.display_name,
        active_branch = excluded.active_branch,
        worktree_path = excluded.worktree_path,
        last_seen = datetime('now');
    """
    params = (
        agent["agent_id"],
        agent["display_name"],
        agent.get("active_branch"),
        agent.get("worktree_path")
    )
    conn.execute(sql, params)

def upsert_task(conn: sqlite3.Connection, task: Dict[str, Any]) -> None:
    """Inserts or updates a task with its problem/solution metadata."""
    # Ensure agent exists first to satisfy foreign key
    upsert_agent(conn, {
        "agent_id": task["agent_id"],
        "display_name": task.get("agent_name", task["agent_id"]),
        "active_branch": task.get("git_branch")
    })
    
    sql = """
    INSERT INTO tasks (
        task_id, agent_id, title, problem_statement, root_cause,
        solution_summary, git_branch, commit_sha, status,
        completion_percentage, created_at, completed_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(task_id) DO UPDATE SET
        agent_id = excluded.agent_id,
        title = excluded.title,
        problem_statement = excluded.problem_statement,
        root_cause = excluded.root_cause,
        solution_summary = excluded.solution_summary,
        git_branch = excluded.git_branch,
        commit_sha = excluded.commit_sha,
        status = excluded.status,
        completion_percentage = excluded.completion_percentage,
        completed_at = excluded.completed_at;
    """
    params = (
        task["task_id"],
        task["agent_id"],
        task["title"],
        task.get("problem_statement"),
        task.get("root_cause"),
        task.get("solution_summary"),
        task.get("git_branch"),
        task.get("commit_sha"),
        task.get("status", "IN_PROGRESS"),
        task.get("completion_percentage", 0.0),
        task.get("created_at"),
        task.get("completed_at")
    )
    conn.execute(sql, params)

def link_task_to_node(conn: sqlite3.Connection, task_id: str, node_id: str, action: str = "MODIFIED") -> None:
    """Associates a task with a code entity node."""
    sql = """
    INSERT INTO task_touched_nodes (task_id, node_id, action)
    VALUES (?, ?, ?)
    ON CONFLICT(task_id, node_id) DO UPDATE SET
        action = excluded.action;
    """
    conn.execute(sql, (task_id, node_id, action))
