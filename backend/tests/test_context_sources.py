"""Context intelligence — git context, log summarization, memory digest, behavior."""

from __future__ import annotations

import asyncio

from agentflow import chat_service, config, ponytail, process_runner, task_service
from agentflow.context_intelligence import behavior, git_context, log_context, memory
from agentflow.process_runner import RUNNER, RunRecord


def _ws(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    return ws


# ------------------------------------------------------------------ behavior


def test_policy_mirrors_ponytail_level(monkeypatch):
    monkeypatch.setattr(ponytail, "level", lambda: "full")
    policy = behavior.build_policy()
    assert policy.level == "full"
    assert policy.block == ponytail.block("full") != ""


def test_policy_block_empty_when_off(monkeypatch):
    monkeypatch.setattr(ponytail, "level", lambda: "off")
    policy = behavior.build_policy()
    assert policy.level == "off" and policy.block == ""


# ---------------------------------------------------------------- git context


def test_git_context_outside_repo_is_empty(tmp_path):
    ws = _ws(tmp_path)
    ctx = asyncio.run(git_context.build_git_context(ws))
    assert ctx.isRepo is False and ctx.diff == "" and ctx.changedFiles == []


def test_git_context_includes_changed_files_and_diff(tmp_path):
    ws = _ws(tmp_path)

    async def scenario():
        from agentflow.git_service import _git

        await _git(ws, "init")
        await _git(ws, "config", "user.email", "t@t.t")
        await _git(ws, "config", "user.name", "t")
        (ws / "tracked.py").write_text("x = 1\n")
        await _git(ws, "add", ".")
        await _git(ws, "commit", "-m", "init")
        (ws / "tracked.py").write_text("x = 2  # changed\n")
        return await git_context.build_git_context(ws)

    ctx = asyncio.run(scenario())
    assert ctx.isRepo is True
    assert ctx.changedFiles == ["tracked.py"]
    assert "tracked.py" in ctx.diff and "+x = 2" in ctx.diff


def test_git_context_never_diffs_tracked_env_files(tmp_path):
    ws = _ws(tmp_path)

    async def scenario():
        from agentflow.git_service import _git

        await _git(ws, "init")
        await _git(ws, "config", "user.email", "t@t.t")
        await _git(ws, "config", "user.name", "t")
        (ws / ".env").write_text("PLAIN=oldvalue\n")
        await _git(ws, "add", "-f", ".env")
        await _git(ws, "commit", "-m", "init")
        (ws / ".env").write_text("PLAIN=supersecret123\n")
        return await git_context.build_git_context(ws)

    ctx = asyncio.run(scenario())
    assert ctx.changedFiles == [".env"]  # the NAME may be listed…
    assert "supersecret123" not in ctx.diff  # …the contents never


# ---------------------------------------------------------------- log context


def test_log_context_summarizes_buffer_and_runs(monkeypatch):
    monkeypatch.setattr(process_runner, "LOG_BUFFER", [])
    monkeypatch.setattr(process_runner, "_view_cleared_at", None)
    process_runner.add_log_entry("task", "step finished cleanly")
    process_runner.add_log_entry("system", "provider wedged", status="error")
    record = RunRecord(id="ctxrun1", argv=["echo", "hi"], cwd=".", status="failed", exit_code=2)
    record.stdout_parts.append("Error: missing token file at line 42\n")
    monkeypatch.setitem(RUNNER.runs, "ctxrun1", record)
    try:
        ctx = log_context.build_log_context()
    finally:
        RUNNER.runs.pop("ctxrun1", None)
    assert "activity_log" in ctx.sources and "run_records" in ctx.sources
    assert "provider wedged" in ctx.summary
    assert "ctxrun1" in ctx.summary and "missing token file at line 42" in ctx.summary
    assert ctx.entryCount == 2


def test_log_context_never_touches_terminal_scrollback():
    import inspect

    source = inspect.getsource(log_context)
    assert "TERMINALS" not in source and "terminal_service" not in source


# -------------------------------------------------------------------- memory


def test_memory_digest_from_chat_and_tasks(tmp_path):
    ws = _ws(tmp_path)
    chat_service.append_message(ws, "user", "please fix the ranker")
    chat_service.append_message(ws, "assistant", "on it — starting with file_ranker.py")
    task_service.create_task(ws, "Fix ranker", "make ranking deterministic")
    mem = memory.build_memory_context(ws)
    assert any("fix the ranker" in line for line in mem.chatLines)
    assert any("Fix ranker" in line for line in mem.taskLines)

    digest = memory.build_session_digest(mem)
    assert digest.sources == ["chat", "tasks"]
    assert "Recent controller chat:" in digest.text and "Recent task state:" in digest.text


def test_memory_is_truncation_only(tmp_path):
    ws = _ws(tmp_path)
    long_message = "x" * 2000
    chat_service.append_message(ws, "user", long_message)
    mem = memory.build_memory_context(ws)
    assert all(len(line) <= memory.CHAT_CLIP_CHARS + 40 for line in mem.chatLines)


def test_memory_empty_workspace_is_empty(tmp_path):
    ws = _ws(tmp_path)
    mem = memory.build_memory_context(ws)
    assert mem.chatLines == [] and mem.taskLines == []
    assert memory.build_session_digest(mem).text == ""
