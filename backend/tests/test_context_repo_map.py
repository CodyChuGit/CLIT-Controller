"""Context intelligence — repo map: ignored dirs, .env refusal, confinement, symbols."""

from __future__ import annotations

from agentflow import config
from agentflow.context_intelligence import repo_map


def _ws(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    return ws


def test_repo_map_lists_code_files_with_symbols(tmp_path):
    ws = _ws(tmp_path)
    (ws / "compressor.py").write_text("class TokenPacker:\n    pass\n\ndef pack_tokens():\n    pass\n")
    (ws / "widget.tsx").write_text("export function Widget() {}\nexport const WIDGET_SIZE = 3\nfunction hidden() {}\n")
    result = repo_map.build_repo_map(ws)
    by_path = {e.path: e for e in result.entries}
    assert by_path["compressor.py"].language == "python"
    assert by_path["compressor.py"].symbols == ["TokenPacker", "pack_tokens"]
    assert by_path["widget.tsx"].symbols == ["Widget", "WIDGET_SIZE"]  # non-exported excluded
    assert result.fileCount == len(result.entries)


def test_repo_map_skips_ignored_and_extra_ignored_dirs(tmp_path):
    ws = _ws(tmp_path)
    (ws / "node_modules").mkdir()
    (ws / "node_modules" / "dep.js").write_text("export const x = 1\n")
    (ws / "coverage").mkdir()
    (ws / "coverage" / "report.py").write_text("x = 1\n")
    (ws / "app.py").write_text("x = 1\n")
    paths = {e.path for e in repo_map.build_repo_map(ws).entries}
    assert "app.py" in paths
    assert not any(p.startswith(("node_modules/", "coverage/", ".agentflow/")) for p in paths)


def test_repo_map_refuses_env_files(tmp_path):
    ws = _ws(tmp_path)
    (ws / ".env").write_text("API_KEY=supersecret\n")
    (ws / ".env.local").write_text("TOKEN=alsosecret\n")
    (ws / ".env.example").write_text("API_KEY=fill-me-in\n")
    entries = {e.path for e in repo_map.build_repo_map(ws).entries}
    assert ".env" not in entries and ".env.local" not in entries
    assert ".env.example" in entries


def test_repo_map_symbols_survive_syntax_errors(tmp_path):
    ws = _ws(tmp_path)
    (ws / "broken.py").write_text("def broken(:\n")
    result = repo_map.build_repo_map(ws)
    assert {e.path for e in result.entries} == {"broken.py"}
    assert result.entries[0].symbols == []


def test_symbol_reader_is_confined_to_workspace(tmp_path):
    ws = _ws(tmp_path)
    # The reader seam (workspace.read_text_file) raises on escapes; the repo map
    # must swallow that into "no symbols", never read outside the workspace.
    assert repo_map._symbols_for(ws, "../outside.py", "python") == []
