"""codebase-memory-mcp wrapper — tested against a fake binary (offline)."""

from __future__ import annotations

import stat
import textwrap

import pytest
from agentflow import memory_service

# Fake binary emitting the REAL tool shapes. list_projects roots the project at
# {root} (substituted per test); search_graph -> results (nodes only);
# query_graph -> columns/rows (edges).
_FAKE_TMPL = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, sys
    tool = sys.argv[2] if len(sys.argv) > 2 else ""
    ROOT = {root!r}
    print(json.dumps({{
        "index_repository": {{"project": "demo", "nodes": 2, "edges": 1, "status": "ok"}},
        "index_status": {{"project": "demo", "status": "ready", "nodes": 2, "edges": 1}},
        "list_projects": {{"projects": [{{"name": "demo", "root_path": ROOT, "nodes": 2}}]}},
        "get_graph_schema": {{"node_labels": [{{"label": "Function", "count": 2}}], "edge_types": []}},
        "search_graph": {{"total": 2, "results": [
            {{"name": "foo", "qualified_name": "demo.foo", "label": "Function",
              "file_path": "src/foo.py", "in_degree": 0, "out_degree": 1}},
            {{"name": "bar", "qualified_name": "demo.bar", "label": "Function",
              "file_path": "src/bar.py", "in_degree": 1, "out_degree": 0}}
        ]}},
        "query_graph": {{"columns": ["source", "type", "target"],
                         "rows": [["demo.foo", "CALLS", "demo.bar"]], "total": 1}}
    }}.get(tool, {{}})))
    """
)


def _install_fake(tmp_path, monkeypatch, root="/some/workspace"):
    p = tmp_path / "codebase-memory-mcp"
    p.write_text(_FAKE_TMPL.format(root=root))
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv(memory_service.BIN_ENV, str(p))
    return p


def test_available_true_with_fake(tmp_path, monkeypatch):
    _install_fake(tmp_path, monkeypatch)
    assert memory_service.available() is True


def test_index_and_status(tmp_path, monkeypatch):
    _install_fake(tmp_path, monkeypatch)
    assert memory_service.index("/some/workspace")["project"] == "demo"
    assert memory_service.status("demo")["status"] == "ready"


def test_resolve_project_matches_root(tmp_path, monkeypatch):
    root = str(tmp_path)
    _install_fake(tmp_path, monkeypatch, root=root)
    assert memory_service.resolve_project(root) == "demo"
    assert memory_service.resolve_project("/not/indexed") is None


def test_graph_nodes_from_results_edges_from_query(tmp_path, monkeypatch):
    _install_fake(tmp_path, monkeypatch)
    g = memory_service.graph("demo", label="Function")
    assert {n["id"] for n in g["nodes"]} == {"demo.foo", "demo.bar"}
    foo = next(n for n in g["nodes"] if n["id"] == "demo.foo")
    assert foo["file"] == "src/foo.py"
    assert foo["degree"] == 1  # in_degree + out_degree
    assert g["edges"] == [{"source": "demo.foo", "target": "demo.bar", "type": "CALLS"}]


def test_missing_binary_raises(tmp_path, monkeypatch):
    monkeypatch.setenv(memory_service.BIN_ENV, str(tmp_path / "nope"))
    with pytest.raises(memory_service.MemoryUnavailable):
        memory_service.status("demo")


class _FakeResp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *_: object) -> bool:
        return False


def test_layout_proxies_the_running_sidecar(monkeypatch):
    monkeypatch.setattr(memory_service, "ensure_ui", lambda: {"available": True, "running": True, "url": "x"})
    monkeypatch.setattr(
        memory_service.urllib.request,
        "urlopen",
        lambda *_a, **_k: _FakeResp(b'{"nodes": [], "edges": []}'),
    )
    assert memory_service.layout("demo", 100) == {"nodes": [], "edges": []}


def test_layout_raises_when_sidecar_down(monkeypatch):
    monkeypatch.setattr(memory_service, "ensure_ui", lambda: {"available": True, "running": False, "url": None})
    with pytest.raises(memory_service.MemoryUnavailable):
        memory_service.layout("demo")
