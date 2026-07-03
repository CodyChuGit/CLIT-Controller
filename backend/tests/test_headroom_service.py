"""Pillar 1 tests — Headroom as an in-process library, always fail-open.

The proxy integration was retired: Headroom now compresses bulky context blocks
inside the prompts CLITC builds (consult tails, task-state summaries), scoped to
CLITC's own CLI runs. These encode the acceptance criteria: on by default,
never required, instructions never rewritten, and any failure returns the
original text unchanged.
"""

from __future__ import annotations

import asyncio

from agentflow import config, headroom_service

ENABLED = {"enabled": True, "minChars": 100}
DISABLED = {**ENABLED, "enabled": False}

LOGGY = "\n".join(f"2026-07-03T10:00:{i % 60:02d} INFO server line {i} — same shape payload id={i}" for i in range(200))


def test_enabled_by_default():
    # Primary token-reduction path: on by default (hermetic test home has no
    # config), still fail-open when the library is missing or errors.
    assert headroom_service.settings()["enabled"] is True


def test_disabled_returns_original(monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: DISABLED)
    assert asyncio.run(headroom_service.compress_context(LOGGY)) == LOGGY


def test_short_context_is_left_alone(monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: ENABLED)
    assert asyncio.run(headroom_service.compress_context("tiny", instructions="x")) == "tiny"


def test_missing_library_fails_open(monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: ENABLED)
    monkeypatch.setattr(headroom_service, "installed", lambda: False)
    assert asyncio.run(headroom_service.compress_context(LOGGY)) == LOGGY


def test_compressor_exception_fails_open(monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: ENABLED)

    def boom(text, instructions):
        raise RuntimeError("compressor exploded")

    monkeypatch.setattr(headroom_service, "_compress_sync", boom)
    assert asyncio.run(headroom_service.compress_context(LOGGY)) == LOGGY


def test_zero_savings_returns_original(monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: ENABLED)
    monkeypatch.setattr(headroom_service, "_compress_sync", lambda text, instructions: None)
    assert asyncio.run(headroom_service.compress_context(LOGGY)) == LOGGY


def test_real_library_crushes_loggy_context(monkeypatch):
    """End-to-end through the actual headroom package: repetitive machine output
    compresses substantially and the stats counters advance."""
    monkeypatch.setattr(headroom_service, "settings", lambda: ENABLED)
    before_saved = headroom_service._stats["tokensSaved"]
    out = asyncio.run(headroom_service.compress_context(LOGGY, instructions="What failed?"))
    assert len(out) < len(LOGGY) / 2
    assert headroom_service._stats["tokensSaved"] > before_saved


def test_config_persists_headroom_settings(tmp_path):
    config.update_settings(headroom={"enabled": False, "minChars": 9000})
    s = headroom_service.settings()
    assert s["enabled"] is False and s["minChars"] == 9000


def test_status_shape(monkeypatch):
    monkeypatch.setattr(headroom_service, "settings", lambda: DISABLED)
    st = headroom_service.status()
    assert st["enabled"] is False
    assert st["mode"] == "local"
    assert st["installed"] is True  # headroom-ai is a backend dependency
    assert "tokensSaved" in st and "callsCompressed" in st
