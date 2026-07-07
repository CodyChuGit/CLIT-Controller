"""codebase-memory-mcp integration — query the code knowledge graph via CLI mode.

The binary indexes a repo into a SQLite knowledge graph and answers queries as
JSON: ``codebase-memory-mcp cli <tool> '<json_args>'``. We render our own themed
graph tab, so only the STANDARD binary is needed (no UI variant, no MCP stdio).

Output field names vary slightly across binary versions, so :func:`_normalize_graph`
is deliberately tolerant. The binary path is resolved from ``$CODEBASE_MEMORY_MCP_BIN``
(tests point this at a fake) or ``codebase-memory-mcp`` on PATH.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Optional

BIN_ENV = "CODEBASE_MEMORY_MCP_BIN"
DEFAULT_BIN = "codebase-memory-mcp"
_TIMEOUT = 120


class MemoryUnavailable(RuntimeError):
    """Raised when the binary is missing or a query fails."""


def binary() -> Optional[str]:
    explicit = os.environ.get(BIN_ENV)
    if explicit:
        return explicit if os.path.exists(explicit) else None
    return shutil.which(DEFAULT_BIN)


def available() -> bool:
    return binary() is not None


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


def index(path: str) -> dict:
    return _run("index_repository", {"path": path})


def status() -> dict:
    return _run("index_status")


def list_projects() -> Any:
    return _run("list_projects")


def schema() -> dict:
    return _run("get_graph_schema")


def architecture() -> dict:
    return _run("get_architecture")


def snippet(qualified_name: str) -> dict:
    return _run("get_code_snippet", {"qualified_name": qualified_name})


def trace(qualified_name: str, depth: int = 2) -> dict:
    return _run("trace_path", {"qualified_name": qualified_name, "depth": depth})


def query(cypher: str) -> dict:
    return _run("query_graph", {"query": cypher})


def graph(label: Optional[str] = None, name: Optional[str] = None, limit: int = 200) -> dict:
    """Return render-ready ``{nodes, edges}`` from search_graph."""
    args: dict = {"limit": limit}
    if label:
        args["label"] = label
    if name:
        args["name"] = name
    return _normalize_graph(_run("search_graph", args))


def _first(d: dict, *keys: str) -> Any:
    for k in keys:
        if d.get(k) is not None:
            return d[k]
    return None


def _normalize_graph(raw: Any) -> dict:
    """Normalize search_graph output to a stable render shape, tolerating the
    field-name variations seen across binary versions.

    -> {nodes: [{id, label, name, file, degree}], edges: [{source, target, type}]}
    """
    if not isinstance(raw, dict):
        return {"nodes": [], "edges": []}
    nodes_in = raw.get("nodes") or []
    edges_in = raw.get("edges") or raw.get("relationships") or raw.get("links") or []

    nodes = []
    for n in nodes_in:
        if not isinstance(n, dict):
            continue
        nid = _first(n, "id", "qualified_name", "qualifiedName", "name")
        if nid is None:
            continue
        labels = n.get("labels")
        label = n.get("label") or (labels[0] if isinstance(labels, list) and labels else None) or "Node"
        nodes.append(
            {
                "id": str(nid),
                "label": label,
                "name": _first(n, "name", "qualified_name", "qualifiedName") or str(nid),
                "file": _first(n, "file", "path", "filePath"),
                "degree": n.get("degree", 0),
            }
        )

    edges = []
    for e in edges_in:
        if not isinstance(e, dict):
            continue
        src = _first(e, "source", "from", "start", "src")
        dst = _first(e, "target", "to", "end", "dst")
        if src is None or dst is None:
            continue
        edges.append(
            {
                "source": str(src),
                "target": str(dst),
                "type": _first(e, "type", "rel", "relationship", "label") or "REL",
            }
        )
    return {"nodes": nodes, "edges": edges}
