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
