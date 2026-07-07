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


@router.get("/status")
def status() -> dict:
    if not memory_service.available():
        return {"available": False, "detail": "codebase-memory-mcp is not installed"}
    return {"available": True, "index": _guard(memory_service.status)}


@router.post("/index")
def index() -> Any:
    ws = require_workspace()
    return _guard(lambda: memory_service.index(str(ws)))


@router.get("/graph")
def graph(label: Optional[str] = None, name: Optional[str] = None, limit: int = 200) -> Any:
    return _guard(lambda: memory_service.graph(label=label, name=name, limit=limit))


@router.get("/schema")
def schema() -> Any:
    return _guard(memory_service.schema)


@router.get("/architecture")
def architecture() -> Any:
    return _guard(memory_service.architecture)


@router.get("/snippet")
def snippet(qname: str) -> Any:
    return _guard(lambda: memory_service.snippet(qname))


@router.get("/trace")
def trace(qname: str, depth: int = 2) -> Any:
    return _guard(lambda: memory_service.trace(qname, depth))


@router.get("/projects")
def projects() -> Any:
    return _guard(memory_service.list_projects)


@router.post("/query")
def query(body: MemoryQueryBody) -> Any:
    return _guard(lambda: memory_service.query(body.query))
