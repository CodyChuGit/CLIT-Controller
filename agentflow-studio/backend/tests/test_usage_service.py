import json
from pathlib import Path

from agentflow import usage_service


def make_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / ".agentflow").mkdir(parents=True)
    return ws


def test_default_usage_created_and_persisted(tmp_path):
    ws = make_ws(tmp_path)
    data = usage_service.ensure_usage(ws)
    assert data["orchestrationMode"] == "balanced"
    assert data["providers"]["claude"]["health"] == "yellow"
    assert data["providers"]["codex"]["health"] == "green"

    on_disk = json.loads((ws / ".agentflow" / "usage.json").read_text())
    assert on_disk["mode"] == "subscription"


def test_mode_and_health_updates(tmp_path):
    ws = make_ws(tmp_path)
    usage_service.set_orchestration_mode(ws, "budget_saver")
    usage_service.set_provider_health(ws, "claude", "red")
    data = usage_service.get_usage(ws)
    assert data["orchestrationMode"] == "budget_saver"
    assert data["providers"]["claude"]["health"] == "red"
    assert data["providers"]["claude"]["manualBudgetLevel"] == "exhausted"


def test_record_call_and_counters(tmp_path):
    ws = make_ws(tmp_path)
    usage_service.record_call(ws, "codex", prompt_chars=1200, output_chars=300, duration_ms=4500, status="succeeded")
    usage_service.increment_avoided(ws)
    usage_service.increment_local_steps(ws)
    data = usage_service.get_usage(ws)
    codex = data["providers"]["codex"]
    assert codex["callsToday"] == 1
    assert codex["estimatedPromptChars"] == 1200
    assert codex["lastCommandDuration"] == 4500
    assert data["expensiveCallsAvoided"] == 1
    assert data["localStepsCompleted"] == 1
