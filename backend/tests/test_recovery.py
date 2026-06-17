"""Restart recovery: a backend restart must never leave state stuck `running`."""

from pathlib import Path

from agentflow import config, queue_service, state_store, task_service
from agentflow.process_runner import RUNNER, RunRecord

DEAD_PID = 2_000_000_000  # not a live process


def setup_interrupted_workspace(tmp_path: Path):
    """A workspace mid-run, as if the backend died: durable run + queue item + step
    all say `running`, but ProcessRunner owns nothing (fresh process)."""
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    tid = task_service.create_task(ws, "Recover me", "Goal.")["id"]

    # A persisted run that was in flight when the backend stopped.
    rec = RunRecord(
        id="run-x",
        argv=["codex", "exec"],
        cwd=str(ws),
        task_id=tid,
        step="codex_spec",
        provider="codex",
        status="running",
    )
    rec.pid = DEAD_PID
    state_store.persist_run(ws, rec.to_ledger(ws))

    # The task step claims to be running, with a full sequence in flight.
    task_service._set_step_state(ws, tid, "codex_spec", status="running", runId="run-x", provider="codex")
    task_service._set_sequence(ws, tid, "running", "codex_spec")

    # Queue: the in-flight item plus a later queued one.
    queue_service.add_steps(ws, tid, ["codex_spec", "claude_implement"])
    data = queue_service.load_queue(ws)
    data["items"][0].update(status="running", runId="run-x")
    queue_service._save(ws, data)

    # Make sure nothing is actually managed (simulates the post-restart runner).
    RUNNER.procs.pop("run-x", None)
    return ws, tid


def test_recovery_settles_run_queue_and_step(tmp_path):
    ws, tid = setup_interrupted_workspace(tmp_path)

    summary = state_store.recover_workspace(ws)
    assert summary == {"runs": 1, "items": 1, "steps": 1}

    # Run is terminal with the right failure kind.
    run = state_store.get_run(ws, "run-x")
    assert run["status"] == "failed" and run["failureKind"] == "backend_restart"

    # Queue item settled; the later step is blocked (not silently runnable).
    items = {i["step"]: i for i in queue_service.load_queue(ws)["items"]}
    assert items["codex_spec"]["status"] == "failed"
    assert items["claude_implement"]["status"] == "blocked"

    # Task step unstuck; full sequence no longer claims to be running.
    meta = task_service._load_meta(ws, tid)
    assert meta["steps"]["codex_spec"]["status"] == "failed"
    assert meta["fullSequence"]["status"] == "interrupted"

    # Durable evidence of the recovery.
    types = [e["type"] for e in state_store.read_events(ws)]
    assert "recovery.completed" in types
    assert "queue.failed" in types


def test_recovery_is_idempotent(tmp_path):
    ws, _ = setup_interrupted_workspace(tmp_path)
    first = state_store.recover_workspace(ws)
    assert any(first.values())
    second = state_store.recover_workspace(ws)
    assert second == {"runs": 0, "items": 0, "steps": 0}


def test_recovery_on_clean_workspace_is_noop(tmp_path):
    ws = tmp_path / "clean"
    ws.mkdir()
    config.ensure_workspace(ws)
    task_service.create_task(ws, "Idle", "Nothing running.")
    assert state_store.recover_workspace(ws) == {"runs": 0, "items": 0, "steps": 0}
