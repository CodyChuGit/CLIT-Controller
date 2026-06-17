"""POST /api/chat/submit — the typed input route (I/O rebuild, frontend stage).

Proves the InputSubmission contract dispatches by destination and that a task
destination carries its taskId end-to-end (the fix for the Tasks-continue bug where
the task id shown in the UI was never sent)."""

from __future__ import annotations

from agentflow import chat_service, config, task_service
from agentflow.app import create_app
from fastapi.testclient import TestClient


def _client(tmp_path) -> TestClient:
    config.set_workspace(str(tmp_path))
    return TestClient(create_app())


def _sub(tmp_path, destination: dict, text: str = "keep going") -> dict:
    return {
        "schemaVersion": "1",
        "id": "s1",
        "workspaceId": str(tmp_path),
        "destination": destination,
        "content": {"text": text, "references": []},
        "createdAt": "2026-06-18T00:00:00Z",
    }


def test_task_destination_passes_focus_task_id(tmp_path, monkeypatch):
    calls: dict = {}

    async def fake_send(ws, message, provider=None, focus_task_id=None):
        calls.update(message=message, focus_task_id=focus_task_id)
        return {"status": "sent"}

    monkeypatch.setattr(chat_service, "send", fake_send)
    r = _client(tmp_path).post(
        "/api/chat/submit", json=_sub(tmp_path, {"kind": "task", "taskId": "task-9", "intent": "continue"})
    )
    assert r.status_code == 200
    assert calls["focus_task_id"] == "task-9"  # the taskId now reaches the backend
    assert calls["message"] == "keep going"


def test_controller_destination_has_no_focus(tmp_path, monkeypatch):
    calls: dict = {}

    async def fake_send(ws, message, provider=None, focus_task_id=None):
        calls.update(focus=focus_task_id)
        return {"status": "sent"}

    monkeypatch.setattr(chat_service, "send", fake_send)
    r = _client(tmp_path).post("/api/chat/submit", json=_sub(tmp_path, {"kind": "controller"}))
    assert r.status_code == 200 and calls["focus"] is None


def test_provider_destination_routes_to_direct(tmp_path, monkeypatch):
    seen: dict = {}

    async def fake_direct(ws, provider, message):
        seen.update(provider=provider, message=message)
        return {"status": "sent"}

    monkeypatch.setattr(chat_service, "send_direct", fake_direct)
    r = _client(tmp_path).post("/api/chat/submit", json=_sub(tmp_path, {"kind": "provider", "provider": "claude"}))
    assert r.status_code == 200 and seen["provider"] == "claude"


def test_invalid_submission_is_422(tmp_path):
    # missing destination → FastAPI validates the InputSubmission and rejects it
    r = _client(tmp_path).post(
        "/api/chat/submit",
        json={
            "schemaVersion": "1",
            "id": "s",
            "workspaceId": str(tmp_path),
            "content": {"text": "x"},
            "createdAt": "t",
        },
    )
    assert r.status_code == 422


def test_focus_task_brief_includes_the_task(tmp_path):
    meta = task_service.create_task(tmp_path, "Add login", "implement login")
    brief = chat_service._focus_task_brief(tmp_path, meta["id"])
    assert meta["id"] in brief and "Add login" in brief and "implement login" in brief
