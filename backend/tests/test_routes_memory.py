"""Memory routes — TestClient over a fake codebase-memory-mcp binary."""

from __future__ import annotations

import stat
import textwrap

from agentflow import memory_service
from agentflow.app import create_app
from fastapi.testclient import TestClient

_FAKE = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, sys
    tool = sys.argv[2] if len(sys.argv) > 2 else ""
    print(json.dumps({
        "index_status": {"status": "ready"},
        "get_graph_schema": {"nodes": 5, "edges": 7},
        "search_graph": {"nodes": [{"id": "a", "label": "Function", "name": "a"}], "edges": []},
    }.get(tool, {})))
    """
)


def _fake(tmp_path, monkeypatch):
    p = tmp_path / "codebase-memory-mcp"
    p.write_text(_FAKE)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv(memory_service.BIN_ENV, str(p))


def test_status_unavailable_without_binary(tmp_path, monkeypatch):
    monkeypatch.setenv(memory_service.BIN_ENV, str(tmp_path / "nope"))
    client = TestClient(create_app())
    r = client.get("/api/memory/status")
    assert r.status_code == 200
    assert r.json()["available"] is False


def test_status_graph_schema_with_fake(tmp_path, monkeypatch):
    _fake(tmp_path, monkeypatch)
    client = TestClient(create_app())
    s = client.get("/api/memory/status").json()
    assert s["available"] is True
    assert s["index"]["status"] == "ready"
    g = client.get("/api/memory/graph", params={"label": "Function"}).json()
    assert g["nodes"][0]["id"] == "a"
    assert g["nodes"][0]["label"] == "Function"
    assert client.get("/api/memory/schema").json()["nodes"] == 5
