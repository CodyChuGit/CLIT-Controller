"""Codebase-memory knowledge-graph API (backed by the codebase-memory-mcp binary)."""

from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import memory_service
from .routes_projects import require_workspace

router = APIRouter()


class MemoryQueryBody(BaseModel):
    query: str


def _guard(call: Callable[[], Any]) -> Any:
    try:
        return call()
    except memory_service.MemoryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _project() -> str:
    """Resolve the indexed project for the current workspace, or 404/503."""
    ws = require_workspace()
    try:
        proj = memory_service.resolve_project(str(ws))
    except memory_service.MemoryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not proj:
        raise HTTPException(status_code=404, detail="workspace not indexed yet — POST /api/memory/index first")
    return proj


@router.get("/status")
def status() -> dict:
    if not memory_service.available():
        return {"available": False, "detail": "codebase-memory-mcp is not installed"}
    ws = require_workspace()
    try:
        proj = memory_service.resolve_project(str(ws))
    except memory_service.MemoryUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    index = _guard(lambda: memory_service.status(proj)) if proj else None
    return {"available": True, "project": proj, "index": index}


@router.get("/ui")
def ui() -> Any:
    """Ensure the built-in graph viewer is running; return its URL for embedding."""
    return _guard(memory_service.ensure_ui)


@router.post("/index")
def index() -> Any:
    ws = require_workspace()
    return _guard(lambda: memory_service.index(str(ws)))


@router.get("/graph")
def graph(label: Optional[str] = None, name: Optional[str] = None, limit: int = 200) -> Any:
    proj = _project()
    return _guard(lambda: memory_service.graph(proj, label=label, name_pattern=name, limit=limit))


@router.get("/layout")
def layout(max_nodes: int = 5000) -> Any:
    """Proxy the viewer's precomputed 3D layout for the current workspace's
    project, so the frontend can render the galaxy natively (no iframe)."""
    proj = _project()
    return _guard(lambda: memory_service.layout(proj, max_nodes))


@router.get("/schema")
def schema() -> Any:
    proj = _project()
    return _guard(lambda: memory_service.schema(proj))


@router.get("/architecture")
def architecture() -> Any:
    proj = _project()
    return _guard(lambda: memory_service.architecture(proj))


@router.get("/snippet")
def snippet(qname: str) -> Any:
    proj = _project()
    return _guard(lambda: memory_service.snippet(proj, qname))


@router.get("/trace")
def trace(qname: str, depth: int = 3) -> Any:
    proj = _project()
    return _guard(lambda: memory_service.trace(proj, qname, depth=depth))


@router.get("/projects")
def projects() -> Any:
    return _guard(memory_service.list_projects)


@router.post("/query")
def query(body: MemoryQueryBody) -> Any:
    proj = _project()
    return _guard(lambda: memory_service.query(proj, body.query))
