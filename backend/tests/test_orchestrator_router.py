"""Task A2 — router returns typed RouteResult/Stage from the engine."""
from __future__ import annotations

from agentflow.orchestrator import router

_AGENTS = {"claude", "codex", "antigravity", "omlx"}


def test_route_for_text_returns_typed_result():
    r = router.route_for_text("implement the core module")
    assert isinstance(r, router.RouteResult)
    assert r.stages and all(isinstance(s, router.Stage) for s in r.stages)
    assert all(s.agent in _AGENTS for s in r.stages)
    assert 0.0 <= r.confidence <= 1.0


def test_explicit_task_type_is_high_confidence():
    r = router.route_for_task("run the tests", task_type="TEST_EXECUTION")
    assert r.decision
    assert r.confidence >= 0.9  # explicit type => 0.95


def test_long_running_attaches_monitor():
    r = router.route_for_task("run the suite", task_type="TEST_EXECUTION", long_running=True)
    assert isinstance(r.monitor, bool)
    assert r.monitor is True
