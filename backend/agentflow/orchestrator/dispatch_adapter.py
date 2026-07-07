"""Task A3 — translate an engine dispatch plan into spawnable stage plans.

Runs the engine's ``dispatch_plan`` in ``cli_only`` mode (AgentComposer spawns
CLIs itself; it never uses Claude-Code plugins), then maps each resolved stage
onto ``{provider_id, model, persona, action, parallel_group}`` that
``process_runner`` can execute. ``parallel_group`` is taken from the *route*
stage (the engine's dispatch entry drops it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import _engine, caps
from .router import RouteResult

_AGENT_TO_PROVIDER = {"codex": "codex", "claude": "claude", "antigravity": "antigravity"}


def _cli_only_policy(ns) -> dict:
    """Full engine dispatch policy (codex/antigravity/omlx sections) with mode
    forced to cli_only — AgentComposer spawns CLIs, never Claude-Code plugins."""
    return {**ns.dispatch.load_policy(), "mode": "cli_only"}


@dataclass
class StagePlan:
    provider_id: Optional[str]  # codex|claude|antigravity, or None for a monitor stage
    model: Optional[str]  # engine tier suggestion; user override wins at exec time
    persona: str
    action: str
    parallel_group: Optional[str] = None
    via: str = ""  # engine mechanism hint (codex_cli|local_script|claude|...)
    monitor: bool = False  # True for an oMLX monitor stage (no provider to spawn)
    fallbacks: list = field(default_factory=list)  # usage fallback hops applied to this stage


def _provider_for(entry: dict) -> Optional[str]:
    agent = str(entry.get("agent") or "")
    mech = str(entry.get("mechanism", ""))
    if agent == "omlx":
        return None
    # A degraded/absorbed stage means the delegate was unavailable -> Claude takes it.
    if agent == "claude" or mech.startswith("claude") or entry.get("via") == "degraded":
        return "claude"
    return _AGENT_TO_PROVIDER.get(agent)


def _model_for(entry: dict) -> Optional[str]:
    agent = entry.get("agent")
    if agent == "antigravity":
        return entry.get("agy_model") or entry.get("model")
    if agent == "codex":
        return entry.get("model")
    return None  # claude: default / user override


def plan(
    route_result: RouteResult,
    *,
    usage_state: Optional[dict] = None,
    caps_override: Optional[dict] = None,
) -> list[StagePlan]:
    """Resolve a route into ordered, spawnable stage plans (with usage fallback)."""
    ns = _engine.load()
    caps_dict = caps_override if caps_override is not None else caps.build_caps()
    dp = ns.dispatch.dispatch_plan(route_result.raw, caps_dict, policy=_cli_only_policy(ns), usage_state=usage_state)
    entries = dp.get("dispatch") or []
    rstages = route_result.stages
    out: list[StagePlan] = []
    for i, entry in enumerate(entries):
        rstage = rstages[i] if i < len(rstages) else None
        fallbacks = []
        if entry.get("fallback_from"):
            fallbacks.append(
                {
                    "from": entry["fallback_from"],
                    "to": entry.get("agent"),
                    "reason": entry.get("fallback_reason", ""),
                }
            )
        out.append(
            StagePlan(
                provider_id=_provider_for(entry),
                model=_model_for(entry),
                persona=entry.get("persona") or (rstage.persona if rstage else ""),
                action=entry.get("action") or (rstage.action if rstage else ""),
                parallel_group=rstage.parallel_group if rstage else None,
                via=entry.get("via", ""),
                monitor=entry.get("agent") == "omlx",
                fallbacks=fallbacks,
            )
        )
    return out
