"""Context intelligence — full pipeline fixture: task in → report out."""

from __future__ import annotations

import asyncio

from agentflow import config, ponytail
from agentflow.context_intelligence import pipeline, prompt_builder, reports
from agentflow.context_intelligence.types import UserTask


def _ws(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    (ws / "tokenizer.py").write_text("def tokenize_text():\n    pass\n\n\nclass TokenizerError(Exception):\n    pass\n")
    (ws / "other.py").write_text("def unrelated():\n    pass\n")
    (ws / "CLAUDE.md").write_text("Always run make verify.\n")
    return ws


def test_full_pipeline_produces_explained_measured_report(tmp_path, monkeypatch):
    monkeypatch.setattr(ponytail, "level", lambda: "full")
    ws = _ws(tmp_path)
    report = asyncio.run(pipeline.run_preview(ws, UserTask(text="fix the tokenizer text bug")))

    assert report.kind == "preview" and report.id and report.createdAt
    assert [f.path for f in report.selectedFiles] == ["tokenizer.py"]
    assert all(f.reasons for f in report.selectedFiles)
    assert report.sectionOrder == list(prompt_builder.SECTION_ORDER)
    assert report.tokenUsage.tokensBefore >= report.tokenUsage.tokensAfter > 0
    assert report.compression, "compression results must be recorded"

    # Preservation guarantees, end to end.
    assert "fix the tokenizer text bug" in report.promptPreview  # user task
    assert "tokenizer.py" in report.promptPreview  # file paths
    assert "tokenize_text" in report.promptPreview  # symbol names
    assert ponytail.block("full") in report.promptPreview  # policy block verbatim
    assert "Always run make verify." in report.promptPreview  # project rules


def test_pipeline_policy_off_leaves_policy_section_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(ponytail, "level", lambda: "off")
    ws = _ws(tmp_path)
    report = asyncio.run(pipeline.run_preview(ws, UserTask(text="fix the tokenizer")))
    assert report.policyLevel == "off"
    assert "## behavior_policy" not in report.promptPreview


def test_pipeline_report_persists_and_reloads(tmp_path):
    ws = _ws(tmp_path)
    report = asyncio.run(pipeline.run_preview(ws, UserTask(text="fix the tokenizer")))
    saved = reports.save_report(ws, report)
    assert (reports.reports_dir(ws) / f"{report.id}.json").is_file()
    loaded = reports.load_report(ws, report.id)
    assert loaded == saved
    assert loaded["task"] == "fix the tokenizer"


def test_persisted_report_is_redacted(tmp_path):
    ws = _ws(tmp_path)
    (ws / "settings.py").write_text('API_KEY = "sk-verysecretkey12345"\ndef settings_loader():\n    pass\n')
    report = asyncio.run(pipeline.run_preview(ws, UserTask(text="update the settings loader")))
    saved = reports.save_report(ws, report)
    raw = (reports.reports_dir(ws) / f"{report.id}.json").read_text()
    assert "sk-verysecretkey12345" not in raw
    assert "sk-verysecretkey12345" not in str(saved)
    assert "[REDACTED]" in raw
