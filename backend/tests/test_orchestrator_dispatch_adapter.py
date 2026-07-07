"""Task A3 — dispatch adapter maps engine plans to spawnable stages (cli_only)."""

from __future__ import annotations

from agentflow.orchestrator import dispatch_adapter, router

# Fixed capabilities so tests don't depend on which CLIs the machine has installed.
ALL_CAPS = {
    "codex_cli": True,
    "codex_plugin": False,
    "agy_cli": True,
    "agy_plugin": False,
    "omlx": False,
}
CLEAN_STATE = {"agents": {}, "events": {}}


def test_plan_returns_spawnable_stages():
    rr = router.route_for_task("run the tests", task_type="TEST_EXECUTION")
    plans = dispatch_adapter.plan(rr, caps_override=ALL_CAPS, usage_state=CLEAN_STATE)
    assert plans
    for p in plans:
        assert isinstance(p, dispatch_adapter.StagePlan)
        assert p.monitor or p.provider_id in {"codex", "claude", "antigravity"}


def test_codex_agentic_stage_carries_gpt55_tier():
    rr = router.route_for_task("analyze the codebase architecture", task_type="CODEBASE_SEMANTIC_ANALYSIS")
    plans = dispatch_adapter.plan(rr, caps_override=ALL_CAPS, usage_state=CLEAN_STATE)
    codex = [p for p in plans if p.provider_id == "codex"]
    assert codex, plans
    assert any(p.model == "gpt-5.5" for p in codex)


def test_exhausted_codex_falls_back_and_records_hop():
    rr = router.route_for_task("run the tests", task_type="TEST_EXECUTION")
    exhausted = {
        "agents": {"codex": {"status": "exhausted", "cooldown_until": 9_999_999_999}},
        "events": {},
    }
    plans = dispatch_adapter.plan(rr, caps_override=ALL_CAPS, usage_state=exhausted)
    # Codex is out -> operations chain moves the stage to antigravity (installed).
    assert any(p.provider_id == "antigravity" for p in plans)
    assert any(p.fallbacks and p.fallbacks[0]["from"] == "codex" for p in plans)
