"""Task A4 — bridge AgentComposer provider health <-> engine usage/exhaustion.

Provider ids (codex/claude/antigravity) map 1:1 onto engine agent names. When a
provider goes RED we mark it exhausted so the engine's spread-first fallback
routes around it; when a run's output shows a rate-limit/quota signal we
auto-detect it, mark the provider exhausted, and return the effective fallback.
"""
from __future__ import annotations

from typing import Optional

from agentflow import provider_probe

from . import _engine


def _installed() -> dict:
    """Engine `resolve()` expects caps keyed by agent name (not codex_cli/…)."""
    return {
        "codex": provider_probe.which("codex") is not None,
        "antigravity": provider_probe.which("antigravity") is not None,
        "omlx": provider_probe.which("omlx") is not None,
    }


def on_provider_health(provider: str, health: str) -> None:
    """RED -> mark the provider exhausted; anything else -> clear (available)."""
    ns = _engine.load()
    state = ns.usage_lib.load_state()
    if str(health).lower() == "red":
        ns.usage_lib.mark(state, provider, "exhausted", reason="provider health RED")
    else:
        ns.usage_lib.mark(state, provider, "available", reason=f"provider health {health}")
    ns.usage_lib.save_state(state)


def on_run_output(provider: str, text: str) -> Optional[str]:
    """Detect a rate-limit/quota signal in run output; if present, mark the
    provider exhausted and return the effective fallback agent (else None)."""
    ns = _engine.load()
    upolicy = ns.usage_lib.load_policy()
    exhausted, cooldown, signal = ns.usage_lib.detect_exhaustion(provider, text, upolicy)
    if not exhausted:
        return None
    state = ns.usage_lib.load_state()
    ns.usage_lib.mark(state, provider, "exhausted", reason=f"detected: {signal}", cooldown=cooldown)
    effective, _hops = ns.usage_lib.resolve(provider, _installed(), state, upolicy)
    ns.usage_lib.save_state(state)
    return effective if effective != provider else None


def snapshot() -> dict:
    """Recent fallback/exhaustion events + delegation counts for the Usage UI."""
    ns = _engine.load()
    events = (ns.usage_lib.load_state() or {}).get("events", {})
    return {
        "fallbacks": (events.get("fallbacks") or [])[-10:],
        "exhaustions": (events.get("exhaustions") or [])[-10:],
        "delegations": events.get("delegations") or {},
    }
