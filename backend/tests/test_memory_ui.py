"""Memory UI sidecar — availability logic (never spawns a real process)."""

from __future__ import annotations

from agentflow import memory_service


def test_ensure_ui_not_available_without_binary(monkeypatch):
    monkeypatch.setattr(memory_service, "binary", lambda: None)
    assert memory_service.ensure_ui() == {"available": False, "running": False, "url": None}


def test_ui_running_false_on_dead_port():
    assert memory_service.ui_running(port=1) is False


def test_ui_url_shape():
    assert memory_service.ui_url(9749) == "http://localhost:9749"
