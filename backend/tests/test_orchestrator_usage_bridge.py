"""Task A4 — usage bridge marks/clears exhaustion and detects it from output.

Each test points the engine's runtime dir at a tmp path so it never touches the
real .claude-runtime state.
"""
from __future__ import annotations

from agentflow.orchestrator import _engine, usage_bridge


def _status(agent: str, state: dict) -> str:
    return _engine.load().usage_lib.effective_status(agent, {agent: True}, state)


def test_red_health_marks_exhausted(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIAGENT_RUNTIME_DIR", str(tmp_path))
    usage_bridge.on_provider_health("codex", "red")
    state = _engine.load().usage_lib.load_state()
    assert _status("codex", state) == "exhausted"


def test_green_health_clears_exhaustion(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIAGENT_RUNTIME_DIR", str(tmp_path))
    usage_bridge.on_provider_health("codex", "red")
    usage_bridge.on_provider_health("codex", "green")
    state = _engine.load().usage_lib.load_state()
    assert _status("codex", state) == "available"


def test_clean_output_is_not_exhaustion(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIAGENT_RUNTIME_DIR", str(tmp_path))
    assert usage_bridge.on_run_output("codex", "all tests passed, no problems") is None


def test_quota_signal_marks_exhausted(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIAGENT_RUNTIME_DIR", str(tmp_path))
    usage_bridge.on_run_output("codex", "Error: quota exceeded, try again later")
    state = _engine.load().usage_lib.load_state()
    assert _status("codex", state) == "exhausted"
    assert isinstance(usage_bridge.snapshot()["exhaustions"], list)
