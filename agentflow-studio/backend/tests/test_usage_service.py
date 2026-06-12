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


def test_window_reset_and_limits(tmp_path):
    from datetime import datetime, timedelta, timezone

    ws = make_ws(tmp_path)
    usage_service.set_provider_limit(ws, "claude", 20, 5)
    usage_service.record_call(ws, "claude", 100, 50, 1000, "succeeded")
    data = usage_service.get_usage(ws)
    assert data["providers"]["claude"]["limitCalls"] == 20
    assert data["providers"]["claude"]["callsToday"] == 1

    # age the window past its 5 hours -> counters reset on next read
    stale = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(timespec="seconds")
    data["providers"]["claude"]["windowStartedAt"] = stale
    usage_service._save(ws, data)
    fresh = usage_service.ensure_usage(ws)
    assert fresh["providers"]["claude"]["callsToday"] == 0
    assert fresh["providers"]["claude"]["limitCalls"] == 20  # limit survives resets


def test_extract_rate_limits_brace_matching():
    line = (
        '{"type":"event","payload":{"rate_limits":{"limit_id":"codex","primary":'
        '{"used_percent":32.0,"window_minutes":300,"resets_at":1781279261},'
        '"secondary":{"used_percent":15.0,"window_minutes":10080,"resets_at":1781847311},'
        '"plan_type":"plus"}}}'
    )
    rl = usage_service._extract_rate_limits(line)
    assert rl is not None
    assert rl["primary"]["used_percent"] == 32.0
    assert rl["plan_type"] == "plus"
    assert usage_service._window_label(300) == "5h"
    assert usage_service._window_label(10080) == "7d"
    assert usage_service._extract_rate_limits("no limits here") is None
