"""Memory routes — called directly with require_workspace patched (suite idiom)."""

from __future__ import annotations

import stat
import textwrap

import pytest
from agentflow import memory_service
from agentflow.api import routes_memory
from fastapi import HTTPException

_FAKE_TMPL = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, sys
    tool = sys.argv[2] if len(sys.argv) > 2 else ""
    ROOT = {root!r}
    print(json.dumps({{
        "index_status": {{"project": "demo", "status": "ready"}},
        "list_projects": {{"projects": [{{"name": "demo", "root_path": ROOT}}]}},
        "search_graph": {{"results": [
            {{"qualified_name": "demo.foo", "name": "foo", "label": "Function",
              "file_path": "foo.py", "in_degree": 0, "out_degree": 1}},
            {{"qualified_name": "demo.bar", "name": "bar", "label": "Function",
              "file_path": "bar.py", "in_degree": 1, "out_degree": 0}}
        ]}},
        "query_graph": {{"columns": ["source", "type", "target"],
                         "rows": [["demo.foo", "CALLS", "demo.bar"]]}}
    }}.get(tool, {{}})))
    """
)


def _fake(tmp_path, monkeypatch, root):
    p = tmp_path / "codebase-memory-mcp"
    p.write_text(_FAKE_TMPL.format(root=root))
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv(memory_service.BIN_ENV, str(p))


def test_status_unavailable_without_binary(tmp_path, monkeypatch):
    monkeypatch.setenv(memory_service.BIN_ENV, str(tmp_path / "nope"))
    assert routes_memory.status()["available"] is False


def test_status_and_graph_with_indexed_workspace(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    _fake(tmp_path, monkeypatch, root=str(ws))
    monkeypatch.setattr(routes_memory, "require_workspace", lambda: ws)

    s = routes_memory.status()
    assert s["available"] is True
    assert s["project"] == "demo"

    g = routes_memory.graph(label="Function")
    assert {n["id"] for n in g["nodes"]} == {"demo.foo", "demo.bar"}
    assert g["edges"] == [{"source": "demo.foo", "target": "demo.bar", "type": "CALLS"}]


def test_graph_404_when_workspace_not_indexed(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    _fake(tmp_path, monkeypatch, root="/different/root")  # resolve_project -> None
    monkeypatch.setattr(routes_memory, "require_workspace", lambda: ws)
    with pytest.raises(HTTPException) as exc:
        routes_memory.graph()
    assert exc.value.status_code == 404
