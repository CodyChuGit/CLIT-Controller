"""End-to-end run lifecycle with a tiny fake provider (no real CLI):
the durable run ledger and events must capture start and finish."""

import asyncio
import os
import stat
from pathlib import Path

from agentflow import config, provider_probe, state_store, task_service


def _fake_provider(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake_provider.py"
    script.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def _wire(monkeypatch, script: Path):
    # codex is the default provider for the `pm` role (codex_spec).
    monkeypatch.setattr(config, "get_command_templates", lambda: {"codex": f"{script} {{prompt}}"})
    monkeypatch.setattr(config, "get_models", lambda: {})
    monkeypatch.setattr(provider_probe, "resolve_executable", lambda a: str(script))


async def _run_and_wait(ws, tid, step):
    result = await task_service.run_step(ws, tid, step, source="manual")
    assert result["status"] == "started"
    run_id = result["runId"]
    for _ in range(100):  # ~5s budget
        run = state_store.get_run(ws, run_id)
        if run and run["status"] != "running":
            return run
        await asyncio.sleep(0.05)
    raise AssertionError("run did not finish in time")


def test_successful_run_is_persisted_with_events(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    tid = task_service.create_task(ws, "Live run", "Goal.")["id"]
    _wire(monkeypatch, _fake_provider(tmp_path, "print('spec done')\n"))

    run = asyncio.run(_run_and_wait(ws, tid, "codex_spec"))
    assert run["status"] == "succeeded"
    assert run["failureKind"] is None
    assert run["commandPreview"] and run["logFile"] and run["promptFile"]

    # Step reflects success; durable events bracket the run.
    meta = task_service._load_meta(ws, tid)
    assert meta["steps"]["codex_spec"]["status"] == "succeeded"
    types = [e["type"] for e in state_store.read_events(ws)]
    assert "run.started" in types and "run.finished" in types
    # A completed run is visible via the merged task-detail accessor (survives restart).
    assert any(r["id"] == run["id"] for r in task_service.task_runs(ws, tid))


def test_failed_run_records_exit_nonzero(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    tid = task_service.create_task(ws, "Failing run", "Goal.")["id"]
    _wire(monkeypatch, _fake_provider(tmp_path, "import sys\nsys.exit(3)\n"))

    run = asyncio.run(_run_and_wait(ws, tid, "codex_spec"))
    assert run["status"] == "failed"
    assert run["failureKind"] == "exit_nonzero"
    assert run["exitCode"] == 3
