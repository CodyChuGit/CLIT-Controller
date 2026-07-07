"""Task A1 — the engine loader imports the pure-stdlib core and caps maps cleanly."""

from __future__ import annotations

from agentflow.orchestrator import _engine, caps


def test_engine_exposes_public_api():
    ns = _engine.load()
    assert hasattr(ns.route_task, "route"), "route-task.py must expose route()"
    assert hasattr(ns.dispatch, "dispatch_plan"), "dispatch.py must expose dispatch_plan()"
    assert hasattr(ns.usage_lib, "resolve")
    assert hasattr(ns.monitor_lib, "classify_deterministic")


def test_engine_load_is_cached():
    assert _engine.load() is _engine.load()


def test_route_returns_stages():
    ns = _engine.load()
    decision = ns.route_task.route(text="implement the core module")
    assert decision["stages"], decision
    assert decision["confidence"] > 0


def test_build_caps_shape():
    c = caps.build_caps()
    assert set(c) == {"codex_cli", "codex_plugin", "agy_cli", "agy_plugin", "omlx"}
    assert c["codex_plugin"] is False and c["agy_plugin"] is False
    assert all(isinstance(v, bool) for v in c.values())
