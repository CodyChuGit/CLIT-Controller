"""Context intelligence — file ranking: reasons, rejected candidates, caps."""

from __future__ import annotations

from agentflow import config
from agentflow.context_intelligence import file_ranker, repo_map


def _ws(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    return ws


def test_ranker_selects_relevant_files_with_reasons(tmp_path):
    ws = _ws(tmp_path)
    (ws / "compressor.py").write_text("def compress_context():\n    pass\n")
    (ws / "unrelated.py").write_text("def greet():\n    pass\n")
    rmap = repo_map.build_repo_map(ws)
    selection = file_ranker.rank_files(ws, "improve the compressor token logic", rmap, changed_files=[])
    assert [f.path for f in selection.selected] == ["compressor.py"]
    top = selection.selected[0]
    assert top.reasons and any("path" in r for r in top.reasons)
    assert "compress_context" in top.excerpt


def test_ranker_reports_rejected_candidates_with_reasons(tmp_path):
    ws = _ws(tmp_path)
    for i in range(12):
        (ws / f"ranker_helper_{i}.py").write_text(f"def ranker_{i}():\n    pass\n")
    rmap = repo_map.build_repo_map(ws)
    selection = file_ranker.rank_files(ws, "fix the ranker helper", rmap, changed_files=[])
    assert len(selection.selected) == file_ranker.TOP_N_FILES
    assert selection.rejected, "losing candidates must be reported"
    assert all(c.reason for c in selection.rejected)
    assert len(selection.rejected) <= file_ranker.TOP_N_REJECTED


def test_git_changed_files_outrank_name_matches(tmp_path):
    ws = _ws(tmp_path)
    (ws / "parser.py").write_text("def parse():\n    pass\n")
    (ws / "state.py").write_text("def tick():\n    pass\n")
    rmap = repo_map.build_repo_map(ws)
    selection = file_ranker.rank_files(ws, "fix the parser bug", rmap, changed_files=["state.py"])
    paths = [f.path for f in selection.selected]
    assert set(paths) == {"parser.py", "state.py"}
    changed = next(f for f in selection.selected if f.path == "state.py")
    assert "changed in git working tree" in changed.reasons


def test_ranker_never_dumps_the_whole_repo(tmp_path):
    ws = _ws(tmp_path)
    for i in range(40):
        (ws / f"widget_{i}.py").write_text("def widget():\n    pass\n")
    rmap = repo_map.build_repo_map(ws)
    selection = file_ranker.rank_files(ws, "update every widget module", rmap, changed_files=[])
    assert len(selection.selected) <= file_ranker.TOP_N_FILES


def test_excerpts_are_trimmed(tmp_path):
    ws = _ws(tmp_path)
    (ws / "bigmod.py").write_text("def bigmod():\n    pass\n" + ("# filler\n" * 3000))
    rmap = repo_map.build_repo_map(ws)
    selection = file_ranker.rank_files(ws, "refactor bigmod", rmap, changed_files=[])
    top = selection.selected[0]
    assert top.excerptTruncated
    assert len(top.excerpt) <= file_ranker.EXCERPT_CHARS + 50
