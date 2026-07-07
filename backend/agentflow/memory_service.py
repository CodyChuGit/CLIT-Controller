"""codebase-memory-mcp integration — query the code knowledge graph via CLI mode.

``codebase-memory-mcp cli <tool> '<json_args>'``. Most tools require a ``project``
name (produced by ``index_repository`` / listed by ``list_projects``), so this
service resolves the project for a workspace by matching indexed root paths.
We render our own themed tab, so only the STANDARD binary is needed.

Verified against the binary source (2026-07). ``search_graph`` returns nodes only
(``results``) — edges are assembled best-effort from ``query_graph``. The exact
Cypher dialect and the default (non-``--json``) output framing should be
reconfirmed on a real install; parsing here is deliberately tolerant.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
from typing import Any, Optional

BIN_ENV = "CODEBASE_MEMORY_MCP_BIN"
DEFAULT_BIN = "codebase-memory-mcp"
_TIMEOUT = 300  # indexing a large repo is slow

# Relationships aren't emitted by search_graph; pull them from the graph directly.
_EDGE_CYPHER = (
    "MATCH (a)-[r]->(b) RETURN a.qualified_name AS source, type(r) AS type, b.qualified_name AS target LIMIT 1000"
)


class MemoryUnavailable(RuntimeError):
    """Raised when the binary is missing or a query fails."""


def binary() -> Optional[str]:
    explicit = os.environ.get(BIN_ENV)
    if explicit:
        return explicit if os.path.exists(explicit) else None
    found = shutil.which(DEFAULT_BIN)
    if found:
        return found
    # The official installer defaults to ~/.local/bin, which isn't always on PATH.
    fallback = os.path.expanduser(f"~/.local/bin/{DEFAULT_BIN}")
    return fallback if os.access(fallback, os.X_OK) else None


def available() -> bool:
    return binary() is not None


# --- graph UI sidecar (the binary's built-in :9749 viewer) -----------------

UI_PORT = 9749
_ui_proc: Optional["subprocess.Popen[bytes]"] = None


def ui_url(port: int = UI_PORT) -> str:
    return f"http://localhost:{port}"


def ui_running(port: int = UI_PORT) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def ensure_ui(port: int = UI_PORT) -> dict:
    """Ensure codebase-memory-mcp's built-in graph viewer is serving on ``port``.

    The UI runs as a thread inside the MCP stdio server, so we spawn the binary
    with stdin held open (never written/closed) so the server — and its viewer —
    stays alive. Idempotent: only starts a process if nothing is serving yet.
    """
    exe = binary()
    if not exe:
        return {"available": False, "running": False, "url": None}
    if ui_running(port):
        return {"available": True, "running": True, "url": ui_url(port)}
    global _ui_proc
    if _ui_proc is None or _ui_proc.poll() is not None:
        _ui_proc = subprocess.Popen(
            [exe, "--ui=true", f"--port={port}"],
            stdin=subprocess.PIPE,  # held open -> MCP server (and its UI) stays alive
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    for _ in range(30):
        if ui_running(port):
            break
        time.sleep(0.1)
    return {"available": True, "running": ui_running(port), "url": ui_url(port)}


def stop_ui() -> None:
    global _ui_proc
    if _ui_proc and _ui_proc.poll() is None:
        _ui_proc.terminate()
        try:
            _ui_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _ui_proc.kill()
    _ui_proc = None


def _run(tool: str, args: Optional[dict] = None) -> Any:
    exe = binary()
    if not exe:
        raise MemoryUnavailable(f"{DEFAULT_BIN} is not installed")
    try:
        proc = subprocess.run(
            [exe, "cli", tool, json.dumps(args or {})],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise MemoryUnavailable(f"{tool} timed out after {_TIMEOUT}s") from exc
    if proc.returncode != 0:
        raise MemoryUnavailable(f"{tool} failed: {(proc.stderr or proc.stdout).strip()[:500]}")
    out = proc.stdout.strip()
    if not out:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise MemoryUnavailable(f"{tool} returned non-JSON output") from exc


# --- indexing -------------------------------------------------------------


def index(repo_path: str, mode: str = "full", persistence: bool = False) -> dict:
    return _run("index_repository", {"repo_path": repo_path, "mode": mode, "persistence": persistence})


def status(project: str) -> dict:
    return _run("index_status", {"project": project})


def list_projects() -> list:
    out = _run("list_projects")
    if isinstance(out, dict):
        return out.get("projects") or []
    return out or []


def resolve_project(repo_path: str) -> Optional[str]:
    """Project name whose indexed root matches ``repo_path`` (else None)."""
    target = os.path.realpath(repo_path)
    for p in list_projects():
        root = isinstance(p, dict) and p.get("root_path")
        if root and os.path.realpath(root) == target:
            return p.get("name")
    return None


# --- queries (each requires a project) ------------------------------------


def schema(project: str) -> dict:
    return _run("get_graph_schema", {"project": project})


def architecture(project: str) -> dict:
    return _run("get_architecture", {"project": project})


def snippet(project: str, qualified_name: str) -> dict:
    return _run(
        "get_code_snippet",
        {"project": project, "qualified_name": qualified_name, "include_neighbors": True},
    )


def trace(project: str, function_name: str, direction: str = "both", depth: int = 3) -> dict:
    return _run(
        "trace_path",
        {"project": project, "function_name": function_name, "direction": direction, "depth": depth},
    )


def query(project: str, cypher: str, max_rows: int = 1000) -> dict:
    return _run("query_graph", {"project": project, "query": cypher, "max_rows": max_rows})


def graph(project: str, label: Optional[str] = None, name_pattern: Optional[str] = None, limit: int = 200) -> dict:
    """Render-ready ``{nodes, edges}``: nodes from search_graph, edges from query_graph."""
    args: dict = {"project": project, "limit": limit}
    if label:
        args["label"] = label
    if name_pattern:
        args["name_pattern"] = name_pattern
    return _assemble_graph(project, _run("search_graph", args))


def _assemble_graph(project: str, search_raw: Any) -> dict:
    results = search_raw.get("results") if isinstance(search_raw, dict) else None
    nodes = []
    node_ids: set[str] = set()
    for r in results or []:
        if not isinstance(r, dict):
            continue
        qn = r.get("qualified_name") or r.get("name")
        if not qn:
            continue
        node_ids.add(qn)
        degree = (r.get("in_degree") or 0) + (r.get("out_degree") or 0)
        nodes.append(
            {
                "id": qn,
                "label": r.get("label") or "Node",
                "name": r.get("name") or qn,
                "file": r.get("file_path"),
                "degree": degree,
            }
        )

    edges = []
    try:
        qres = query(project, _EDGE_CYPHER)
        cols = qres.get("columns") or []
        idx = {c: i for i, c in enumerate(cols)}
        si, ti, tyi = idx.get("source"), idx.get("target"), idx.get("type")
        if si is not None and ti is not None:
            for row in qres.get("rows") or []:
                src, dst = row[si], row[ti]
                if src in node_ids and dst in node_ids:
                    etype = row[tyi] if tyi is not None and tyi < len(row) else "REL"
                    edges.append({"source": src, "target": dst, "type": etype or "REL"})
    except MemoryUnavailable:
        pass  # nodes-only graph when the Cypher dialect isn't available

    return {"nodes": nodes, "edges": edges}
