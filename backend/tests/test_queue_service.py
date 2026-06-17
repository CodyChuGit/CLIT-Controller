from pathlib import Path

import pytest
from agentflow import config, queue_service, task_service


def make_task(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    meta = task_service.create_task(ws, "Queue me", "Do queued things.")
    return ws, meta["id"]


def test_add_steps_orders_and_resolves_providers(tmp_path):
    ws, tid = make_task(tmp_path)
    state = queue_service.add_steps(ws, tid, ["codex_spec", "claude_implement"])
    items = state["items"]
    assert [i["step"] for i in items] == ["codex_spec", "claude_implement"]
    assert items[0]["provider"] == "codex"
    assert items[1]["provider"] == "claude"
    assert all(i["status"] == "queued" for i in items)
    assert state["activeCount"] == 2


def test_duplicate_active_steps_are_skipped(tmp_path):
    ws, tid = make_task(tmp_path)
    queue_service.add_steps(ws, tid, ["codex_spec"])
    state = queue_service.add_steps(ws, tid, ["codex_spec", "gemini_qa"])
    assert [i["step"] for i in state["items"]] == ["codex_spec", "gemini_qa"]


def test_unknown_step_or_task_rejected(tmp_path):
    ws, tid = make_task(tmp_path)
    with pytest.raises(ValueError):
        queue_service.add_steps(ws, tid, ["nope_step"])
    with pytest.raises(FileNotFoundError):
        queue_service.add_steps(ws, "no-such-task", ["codex_spec"])


def test_remove_and_clear_keep_running_items(tmp_path):
    ws, tid = make_task(tmp_path)
    state = queue_service.add_steps(ws, tid, ["codex_spec", "gemini_qa"])
    first = state["items"][0]["id"]
    queue_service.remove_item(ws, first)
    data = queue_service.load_queue(ws)
    assert [i["step"] for i in data["items"]] == ["gemini_qa"]
    # mark as running, then clear: running items survive
    data["items"][0]["status"] = "running"
    queue_service._save(ws, data)
    state = queue_service.clear_queue(ws)
    assert len(state["items"]) == 1


def test_queued_event_written_to_task(tmp_path):
    ws, tid = make_task(tmp_path)
    queue_service.add_steps(ws, tid, ["codex_spec"])
    meta = task_service._load_meta(ws, tid)
    assert any(e["type"] == "queued" for e in meta["events"])


def test_summary_line(tmp_path):
    ws, tid = make_task(tmp_path)
    assert queue_service.summary_line(ws) == "Queue: empty"
    queue_service.add_steps(ws, tid, ["codex_spec"])
    line = queue_service.summary_line(ws)
    assert "1 active" in line and "codex_spec" in line


def test_consult_requested_for_orchestrated_tasks(tmp_path):
    ws = tmp_path / "ws2"
    ws.mkdir()
    config.ensure_workspace(ws)
    meta = task_service.create_task(ws, "Orchestrated", "Goal.", orchestrated=True)
    data = queue_service.load_queue(ws)
    item = {"taskId": meta["id"], "label": "Implement", "provider": "claude", "status": "done", "note": None}
    queue_service._request_consult(data, item, None)
    queue_service._request_consult(data, item, None)  # duplicate per task is skipped
    assert len(data["consults"]) == 1
    assert data["consults"][0]["taskId"] == meta["id"]


def test_task_state_summary_reports_agent_work(tmp_path):
    ws = tmp_path / "ws3"
    ws.mkdir()
    config.ensure_workspace(ws)
    meta = task_service.create_task(ws, "Summary", "Goal.")
    m = task_service._load_meta(ws, meta["id"])
    m["steps"]["codex_spec"].update(status="succeeded", artifactsWritten=["01_CODEX_SPEC.md"])
    task_service._save_meta(ws, m)
    summary = task_service.task_state_summary(ws, meta["id"])
    assert "codex_spec" in summary and "wrote 01_CODEX_SPEC.md" in summary
