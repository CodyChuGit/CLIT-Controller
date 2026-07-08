"""Context intelligence — API routes: preview, benchmark, report fetch, guards.

Route functions are called directly with ``require_workspace`` patched,
matching the suite's existing route-test style (test_routes_state).
"""

from __future__ import annotations

import asyncio

import pytest
from agentflow import config
from agentflow.api import routes_context
from fastapi import HTTPException


def _ws(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    (ws / "loader.py").write_text("def load_things():\n    pass\n")
    monkeypatch.setattr(routes_context, "require_workspace", lambda: ws)
    return ws


def test_preview_endpoint_returns_persisted_report(tmp_path, monkeypatch):
    _ws(tmp_path, monkeypatch)
    body = routes_context.ContextPreviewRequest(task="improve the loader")
    out = asyncio.run(routes_context.preview(body))
    assert out["kind"] == "preview"
    assert out["tokenUsage"]["tokensAfter"] > 0
    assert [f["path"] for f in out["selectedFiles"]] == ["loader.py"]
    # and it is fetchable again through the report route
    again = routes_context.get_report(out["id"])
    assert again == out


def test_benchmark_endpoint_runs_three_strategies(tmp_path, monkeypatch):
    _ws(tmp_path, monkeypatch)
    out = asyncio.run(routes_context.benchmark(routes_context.ContextBenchmarkRequest(task="improve the loader")))
    assert out["kind"] == "benchmark"
    assert [r["strategy"] for r in out["benchmark"]] == ["naive", "ranked", "ranked_compressed"]


def test_bad_report_id_is_400_before_filesystem(tmp_path, monkeypatch):
    _ws(tmp_path, monkeypatch)
    for bad in ("../escape", "a/b", "..", "id with space", "%2e%2e"):
        with pytest.raises(HTTPException) as exc:
            routes_context.get_report(bad)
        assert exc.value.status_code == 400


def test_missing_report_is_404(tmp_path, monkeypatch):
    _ws(tmp_path, monkeypatch)
    with pytest.raises(HTTPException) as exc:
        routes_context.get_report("deadbeef")
    assert exc.value.status_code == 404


def test_no_workspace_is_409(monkeypatch):
    # The real require_workspace raises 409 when no workspace is selected; the
    # hermetic global config has none by default.
    with pytest.raises(HTTPException) as exc:
        routes_context.get_report("deadbeef")
    assert exc.value.status_code == 409


def test_router_is_registered_in_app():
    from agentflow.app import create_app

    # openapi()["paths"] is version-agnostic: newer FastAPI keeps included routers
    # as nested objects in app.routes (no top-level .path), but the OpenAPI schema
    # always lists the effective paths.
    paths = set(create_app().openapi()["paths"])
    assert "/api/context/preview" in paths
    assert "/api/context/benchmark" in paths
    assert "/api/context/reports/{report_id}" in paths
