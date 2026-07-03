"""Pillar 1 tests — Headroom integration must be optional, fail-open, and bounded.

These encode the Pillar 1 acceptance criteria (docs/PILLARS.md): Headroom is off by
default, never required, and never delays a spawn; when enabled and reachable it
routes supported agents through the proxy.
"""

from __future__ import annotations

import asyncio
import sys
import time

from agentflow import config, headroom_service
from agentflow.process_runner import ProcessRunner

ENABLED = {"enabled": True, "proxyUrl": "http://127.0.0.1:8799", "savingsProfile": "agent-90"}
DISABLED = {**ENABLED, "enabled": False}


def test_disabled_by_default_returns_empty(monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: DISABLED)
    assert headroom_service.proxy_env("claude") == {}


def test_enabled_but_unreachable_fails_open(monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: ENABLED)
    monkeypatch.setattr(headroom_service, "proxy_reachable", lambda url=None: False)
    assert headroom_service.proxy_env("claude") == {}


def test_routes_claude_to_anthropic_base_url(monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: ENABLED)
    monkeypatch.setattr(headroom_service, "proxy_reachable", lambda url=None: True)
    assert headroom_service.proxy_env("claude") == {"ANTHROPIC_BASE_URL": "http://127.0.0.1:8799"}


def test_routes_codex_to_openai_base_url(monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: ENABLED)
    monkeypatch.setattr(headroom_service, "proxy_reachable", lambda url=None: True)
    assert headroom_service.proxy_env("codex") == {"OPENAI_BASE_URL": "http://127.0.0.1:8799/v1"}


def test_unsupported_providers_not_routed(monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: ENABLED)
    monkeypatch.setattr(headroom_service, "proxy_reachable", lambda url=None: True)
    assert headroom_service.proxy_env("antigravity") == {}
    assert headroom_service.proxy_env(None) == {}


def test_reachability_probe_is_bounded_and_refuses_fast():
    assert headroom_service._PROBE_TIMEOUT <= 0.5
    started = time.monotonic()
    # A closed local port refuses quickly; the point is it never hangs.
    assert headroom_service._tcp_reachable("http://127.0.0.1:9") is False
    assert (time.monotonic() - started) < 2.0


def test_config_persists_headroom_settings(tmp_path):
    config.update_settings(headroom={"enabled": True, "proxyUrl": "http://127.0.0.1:9000"})
    s = headroom_service.settings()
    assert s["enabled"] is True
    assert s["proxyUrl"] == "http://127.0.0.1:9000"
    assert s["savingsProfile"] == "agent-90"  # default preserved when not overridden


def test_status_shape(monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: DISABLED)
    st = headroom_service.status()
    assert st["enabled"] is False and st["reachable"] is False
    assert "claude" in st["routedProviders"] and "codex" in st["routedProviders"]


def test_process_runner_injects_base_url_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: ENABLED)
    monkeypatch.setattr(headroom_service, "proxy_reachable", lambda url=None: True)

    async def go():
        runner = ProcessRunner()
        return await runner.run_and_wait(
            [sys.executable, "-c", "import os;print(os.environ.get('ANTHROPIC_BASE_URL',''))"],
            tmp_path,
            timeout=10,
            provider="claude",
        )

    rec = asyncio.run(go())
    assert "http://127.0.0.1:8799" in rec.stdout
    assert rec.headroom_applied is True


def test_process_runner_runs_direct_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: DISABLED)

    async def go():
        runner = ProcessRunner()
        return await runner.run_and_wait(
            [sys.executable, "-c", "import os;print('BASE=' + os.environ.get('ANTHROPIC_BASE_URL',''))"],
            tmp_path,
            timeout=10,
            provider="claude",
        )

    rec = asyncio.run(go())
    # Disabled → the proxy URL is never injected; the child inherits whatever
    # ambient ANTHROPIC_BASE_URL the operator already had (fail-open / no override).
    assert "8799" not in rec.stdout
    assert rec.headroom_applied is False


# ------------------------------------------------- managed proxy (primary path)


def test_enabled_by_default():
    # Headroom is the PRIMARY token-reduction layer: on by default (hermetic test
    # home has no config), still fail-open when not installed/reachable.
    assert headroom_service.settings()["enabled"] is True


def _no_proxy_running(monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: ENABLED)
    monkeypatch.setattr(headroom_service, "proxy_reachable", lambda url=None: False)
    monkeypatch.setattr(headroom_service, "_proxy_run_id", None)


def test_ensure_proxy_no_spawn_when_not_installed(monkeypatch):
    _no_proxy_running(monkeypatch)
    monkeypatch.setattr(headroom_service, "executable", lambda: None)
    calls: list = []

    async def fake_start(*a, **k):
        calls.append(a)

    monkeypatch.setattr("agentflow.process_runner.RUNNER.start", fake_start)
    st = asyncio.run(headroom_service.ensure_proxy())
    assert calls == []  # fail-open: agents run direct
    assert st["managed"] is False


def test_ensure_proxy_spawns_with_savings_profile(monkeypatch, tmp_path):
    from agentflow.process_runner import RunRecord

    _no_proxy_running(monkeypatch)
    monkeypatch.setattr(headroom_service, "executable", lambda: "/fake/bin/headroom")

    async def fake_profile_env(binary, profile):
        assert profile == "agent-90"
        return {"HEADROOM_PROFILE": profile}

    monkeypatch.setattr(headroom_service, "_savings_profile_env", fake_profile_env)
    started: dict = {}

    async def fake_start(argv, cwd, **kwargs):
        started["argv"] = argv
        started["extra_env"] = kwargs.get("extra_env")
        return RunRecord(id="hr1", argv=argv, cwd=str(cwd)), None

    monkeypatch.setattr("agentflow.process_runner.RUNNER.start", fake_start)
    asyncio.run(headroom_service.ensure_proxy())
    assert started["argv"] == ["/fake/bin/headroom", "proxy", "--port", "8799"]
    assert started["extra_env"] == {"HEADROOM_PROFILE": "agent-90"}
    assert headroom_service._proxy_run_id == "hr1"
    monkeypatch.setattr(headroom_service, "_proxy_run_id", None)  # cleanup


def test_ensure_proxy_skips_when_already_reachable(monkeypatch):
    _no_proxy_running(monkeypatch)
    monkeypatch.setattr(headroom_service, "proxy_reachable", lambda url=None: True)
    calls: list = []

    async def fake_start(*a, **k):
        calls.append(a)

    monkeypatch.setattr("agentflow.process_runner.RUNNER.start", fake_start)
    asyncio.run(headroom_service.ensure_proxy())
    assert calls == []  # a user-run proxy is respected, not duplicated


def test_savings_profile_env_parses_export_lines(monkeypatch):
    from agentflow.process_runner import RunRecord

    record = RunRecord(id="p", argv=["headroom"], cwd=".")
    record.status = "succeeded"
    record.exit_code = 0
    record.stdout_parts = ["export HEADROOM_MODE='aggressive'\nexport HEADROOM_GUARD=0.9\nnot an export\n"]

    async def fake_run_and_wait(*a, **k):
        return record

    monkeypatch.setattr("agentflow.process_runner.RUNNER.run_and_wait", fake_run_and_wait)
    env = asyncio.run(headroom_service._savings_profile_env("headroom", "agent-90"))
    assert env == {"HEADROOM_MODE": "aggressive", "HEADROOM_GUARD": "0.9"}


def test_executable_prefers_our_python_env(monkeypatch, tmp_path):
    """headroom-ai is a backend dependency: the venv console script wins over any
    user-global binary on PATH."""
    fake_bin = tmp_path / "venv" / "bin"
    fake_bin.mkdir(parents=True)
    (fake_bin / "headroom").write_text("#!/bin/sh\n")
    monkeypatch.setattr(sys, "executable", str(fake_bin / "python"))
    assert headroom_service.executable() == str(fake_bin / "headroom")


def test_executable_falls_back_to_path(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "nowhere" / "python"))
    monkeypatch.setattr("agentflow.provider_probe.resolve_executable", lambda name: "/global/headroom")
    assert headroom_service.executable() == "/global/headroom"
