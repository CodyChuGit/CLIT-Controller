import asyncio
from pathlib import Path

from agentflow import config, task_service
from agentflow.process_runner import RunRecord
from agentflow.prompt_templates import TASK_FILES


def make_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "demo-project"
    ws.mkdir()
    config.ensure_workspace(ws)
    return ws


def test_create_task_writes_all_handoff_files(tmp_path):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "Fix playback overlay", "The overlay clips on iPhone SE.")

    folder = ws / ".agentflow" / "tasks" / meta["id"]
    assert folder.is_dir()
    for name in TASK_FILES:
        assert (folder / name).exists(), f"missing {name}"
    assert (folder / "logs").is_dir()
    assert "Fix playback overlay" in (folder / "00_USER_GOAL.md").read_text()


def test_prompts_include_budget_context(tmp_path):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "Add settings toggle", "Add a dark mode toggle.")
    claude_prompt = (ws / ".agentflow" / "tasks" / meta["id"] / "03_CLAUDE_PROMPT.md").read_text()
    assert "Budget context:" in claude_prompt
    assert "Claude usage:" in claude_prompt

    preview = task_service.build_step_preview(ws, meta["id"], "codex_spec")
    assert preview["provider"] == "codex"
    assert "Budget context:" in preview["commandPreview"]


def test_routing_decisions_written(tmp_path):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "Refactor nav", "Tidy the navigation bar.")
    decisions = (ws / ".agentflow" / "tasks" / meta["id"] / "ROUTING_DECISIONS.md").read_text()
    assert "# Routing Decisions" in decisions
    assert "## Budget Context" in decisions
    assert "Traffic control mode:" in decisions


def test_task_listing_and_detail(tmp_path):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "A task", "Do the thing.")
    tasks = task_service.list_tasks(ws)
    assert any(t["id"] == meta["id"] for t in tasks)

    detail = task_service.get_task_detail(ws, meta["id"])
    assert detail["task"]["id"] == meta["id"]
    assert len(detail["files"]) == len(TASK_FILES)
    assert set(detail["stepPreviews"]) == set(task_service.STEP_DEFS)


def test_run_step_rejects_busy_provider(tmp_path, monkeypatch):
    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "A task", "Do the thing.")
    record = RunRecord(id="busy-codex", argv=["codex"], cwd=str(ws), provider="codex", step="chat")
    monkeypatch.setattr(task_service.RUNNER, "runs", {record.id: record})

    result = asyncio.run(task_service.run_step(ws, meta["id"], "codex_spec"))

    assert result["status"] == "provider_busy"
    assert result["runId"] == "busy-codex"


def test_step_exchanges_rebuilt_from_log_files(tmp_path):
    from agentflow import config, paths, task_service

    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    meta = task_service.create_task(ws, "Demo", "demo goal")
    logs = paths.task_logs_dir(ws, meta["id"])
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "20260612-201313-codex_spec.prompt.txt").write_text("spec prompt sk-secret12345678", encoding="utf-8")
    (logs / "20260612-201313-codex_spec.log").write_text("spec output", encoding="utf-8")
    (logs / "20260612-201825-codex_spec.prompt.txt").write_text("second prompt", encoding="utf-8")
    (logs / "20260612-201825-codex_spec.log").write_text("second output", encoding="utf-8")
    # orphaned prompt without a log (run never started) must not break parsing
    (logs / "20260612-201502-claude_implement.prompt.txt").write_text("orphan", encoding="utf-8")

    ex = task_service.step_exchanges(ws, meta["id"])
    spec = ex["codex_spec"]
    assert [e["stamp"] for e in spec] == ["20260612-201313", "20260612-201825"]  # oldest first
    assert spec[0]["output"] == "spec output"
    assert "[REDACTED]" in spec[0]["prompt"] and "sk-secret" not in spec[0]["prompt"]
    assert ex["claude_implement"][0]["output"] == ""


# A run .log file as written by process_runner._write_log_file.
def _log_file(stdout: str, stderr: str = "", status: str = "succeeded", exit_code: int = 0) -> str:
    return (
        "# Command Line Interface Terminal Controller run abc123\n"
        "# command: /opt/homebrew/bin/claude -p 'Budget context: ... big prompt'\n"
        "# cwd: /tmp/ws\n"
        f"# status: {status}  exit: {exit_code}  duration_ms: 100\n"
        f"\n--- STDOUT ---\n{stdout}\n"
        f"\n--- STDERR ---\n{stderr}\n"
    )


def test_extract_log_reply_strips_scaffolding():
    out = task_service._extract_log_reply(_log_file("Wrote 04_CLAUDE_IMPLEMENTATION_SUMMARY.md."))
    assert out == "Wrote 04_CLAUDE_IMPLEMENTATION_SUMMARY.md."
    # The metadata header, echoed command/prompt, and banners are gone.
    assert "Command Line Interface Terminal Controller run" not in out
    assert "Budget context" not in out
    assert "--- STDOUT ---" not in out


def test_extract_log_reply_empty_on_cancelled_run():
    # A cancelled run (exit 143) has empty stdout/stderr — the reply must be empty,
    # not the log scaffolding the user was seeing.
    assert task_service._extract_log_reply(_log_file("", status="cancelled", exit_code=143)) == ""


def test_extract_log_reply_falls_back_to_stderr():
    out = task_service._extract_log_reply(_log_file("", stderr="boom: command failed"))
    assert out == "boom: command failed"


def test_extract_log_reply_passes_through_unknown_format():
    # A log not in the banner format (legacy/plain) is returned as-is, not dropped.
    assert task_service._extract_log_reply("plain output") == "plain output"


def test_step_exchanges_returns_reply_not_log_scaffolding(tmp_path):
    from agentflow import paths

    ws = make_workspace(tmp_path)
    meta = task_service.create_task(ws, "T", "g")
    logs = paths.task_logs_dir(ws, meta["id"])
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "20260101-120000-claude_implement.prompt.txt").write_text("Implement it.", encoding="utf-8")
    (logs / "20260101-120000-claude_implement.log").write_text(
        _log_file("Implemented the scheduler integration."), encoding="utf-8"
    )

    ex = task_service.step_exchanges(ws, meta["id"])
    out = ex["claude_implement"][0]["output"]
    assert out == "Implemented the scheduler integration."
    assert "Command Line Interface Terminal Controller run" not in out
    assert "Budget context" not in out
