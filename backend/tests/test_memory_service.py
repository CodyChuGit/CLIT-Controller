"""codebase-memory-mcp wrapper — tested against a fake binary (offline)."""

from __future__ import annotations

import stat
import textwrap

import pytest
from agentflow import memory_service

# A fake `codebase-memory-mcp` that answers `cli <tool> <json>` with canned JSON.
# Node/edge field names intentionally mixed to exercise _normalize_graph tolerance.
_FAKE = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, sys
    tool = sys.argv[2] if len(sys.argv) > 2 else ""
    print(json.dumps({
        "index_repository": {"status": "indexing", "project": "demo"},
        "index_status": {"status": "ready", "progress": 100},
        "get_graph_schema": {"nodes": 10, "edges": 20},
        "search_graph": {
            "nodes": [
                {"id": "demo.foo", "labels": ["Function"], "name": "foo", "path": "src/foo.py", "degree": 3},
                {"id": "demo.Bar", "label": "Class", "qualified_name": "demo.Bar", "file": "src/bar.py"},
            ],
            "edges": [{"from": "demo.foo", "to": "demo.Bar", "type": "CALLS"}],
        },
    }.get(tool, {})))
    """
)


def _install_fake(tmp_path, monkeypatch):
    p = tmp_path / "codebase-memory-mcp"
    p.write_text(_FAKE)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv(memory_service.BIN_ENV, str(p))


def test_available_true_with_fake(tmp_path, monkeypatch):
    _install_fake(tmp_path, monkeypatch)
    assert memory_service.available() is True


def test_status_and_schema(tmp_path, monkeypatch):
    _install_fake(tmp_path, monkeypatch)
    assert memory_service.status()["status"] == "ready"
    assert memory_service.schema()["nodes"] == 10


def test_graph_normalization_tolerates_field_variants(tmp_path, monkeypatch):
    _install_fake(tmp_path, monkeypatch)
    g = memory_service.graph(label="Function")
    assert {n["id"] for n in g["nodes"]} == {"demo.foo", "demo.Bar"}
    foo = next(n for n in g["nodes"] if n["id"] == "demo.foo")
    assert foo["label"] == "Function"  # from labels[0]
    assert foo["file"] == "src/foo.py"  # from path
    bar = next(n for n in g["nodes"] if n["id"] == "demo.Bar")
    assert bar["label"] == "Class"  # from label
    assert g["edges"] == [{"source": "demo.foo", "target": "demo.Bar", "type": "CALLS"}]


def test_missing_binary_raises(tmp_path, monkeypatch):
    monkeypatch.setenv(memory_service.BIN_ENV, str(tmp_path / "nope"))
    with pytest.raises(memory_service.MemoryUnavailable):
        memory_service.status()
