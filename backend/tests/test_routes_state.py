"""Route-handler tests for the durable-state and queue-op endpoints.

The suite has no HTTP client dependency, so these call the route functions directly with
``require_workspace`` patched — enough to prove wiring (params, status mapping, and the
approval→execute hop) without standing up a server.
"""

import asyncio

import pytest
from agentflow import chat_service, config, queue_service, state_store, task_service
from agentflow.api import routes_queue, routes_state
from fastapi import HTTPException


def _ws(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    config.ensure_workspace(ws)
    monkeypatch.setattr(routes_state, "require_workspace", lambda: ws)
    monkeypatch.setattr(routes_queue, "require_workspace", lambda: ws)
    return ws


def test_events_endpoint_returns_cursor(tmp_path, monkeypatch):
    # /api/events is now backed by the live event bus (global monotonic ids), so
    # assert the resume-by-cursor contract rather than a fixed starting id.
    ws = _ws(tmp_path, monkeypatch)
    state_store.append_event(ws, "task.created", "hi")
    out = routes_state.events(cursor=0)
    assert len(out["events"]) >= 1
    assert out["events"][-1]["type"] == "task.created"
    # Resuming from the returned cursor yields no duplicates.
    assert routes_state.events(cursor=out["cursor"])["events"] == []


def test_run_endpoint_404_then_found(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    with pytest.raises(HTTPException) as exc:
        routes_state.get_run("nope")
    assert exc.value.status_code == 404
    from agentflow.process_runner import RunRecord

    state_store.persist_run(ws, RunRecord(id="r1", argv=["x"], cwd=str(ws), status="succeeded").to_ledger(ws))
    assert routes_state.get_run("r1")["id"] == "r1"


def test_approval_reject_endpoint(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    ap = state_store.create_approval(ws, action="git push", reason="remote")
    out = routes_state.reject(ap["id"])
    assert out["status"] == "rejected"
    assert routes_state.list_approvals()["approvals"][0]["status"] == "rejected"


def test_approval_approve_executes_command(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    ap = state_store.create_approval(ws, action="npm install foo", reason="deps", provider="codex")

    calls = {}

    async def fake_exec(workspace, command, provider, task_id=None, approved=False):
        calls.update(command=command, approved=approved)

    monkeypatch.setattr(chat_service, "execute_run_directive", fake_exec)
    out = asyncio.run(routes_state.approve(ap["id"]))
    assert out["status"] == "approved"
    assert calls == {"command": "npm install foo", "approved": True}  # bypasses the gate
    assert state_store.get_approval(ws, ap["id"])["status"] == "approved"


def test_queue_retry_route(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    tid = task_service.create_task(ws, "T", "G")["id"]
    queue_service.add_steps(ws, tid, ["codex_spec"])
    data = queue_service.load_queue(ws)
    item_id = data["items"][0]["id"]
    data["items"][0]["status"] = "failed"
    queue_service._save(ws, data)
    out = routes_queue.retry(routes_queue.QueueItemRequest(itemId=item_id))
    assert out["status"] == "ok"
    assert queue_service.load_queue(ws)["items"][0]["status"] == "queued"
