#!/usr/bin/env python3
"""usage_lib.py - usage/quota state + fallback-chain resolution.

The skill's goal is to preserve Claude tokens by delegating to Codex / agy /
oMLX. Two things can stop a delegate from taking work:

  * not installed       (capabilities.json, from detect-capabilities.sh)
  * out of usage/quota  (agent-usage.json, "exhausted" with a cooldown)

"usable" = installed AND not exhausted. When the preferred agent for a unit of
work isn't usable, routing walks that work's fallback chain to the next usable
agent; if none remain, Claude takes over (last-resort capacity, while always
keeping final authority).

State lives in `.claude-runtime/agent-usage.json`. This module is imported by
dispatch.py and wrapped by the agent-usage.py CLI; agent-router.sh shells out to
the CLI. Time is injected (`now_ts`) so tests are deterministic.
"""
from __future__ import annotations

import os
import re
import time

import _lib

AGENTS = ["claude", "codex", "antigravity", "omlx"]

# v2 role model: Codex owns local ops/QA/git/Apple; agy (Gemini) owns live
# research + visual QA + summaries; each backs the other up before Claude.
DEFAULT_CHAINS = {
    "research": ["antigravity", "codex", "claude"],
    "analysis": ["codex", "antigravity", "claude"],
    "frontend": ["antigravity", "codex", "claude"],
    "operations": ["codex", "antigravity", "claude"],
    "monitoring": ["omlx", "codex", "antigravity", "claude"],
}
DEFAULT_AGENT_ROLES = {"codex": "operations", "antigravity": "research",
                       "omlx": "monitoring", "claude": "analysis"}
DEFAULT_COOLDOWN = 3600
DEFAULT_SIGNALS = {
    "codex": [r"rate.?limit", r"quota", r"usage limit", r"insufficient_quota",
              r"\b429\b", r"too many requests", r"plan limit", r"upgrade your plan",
              r"you (?:have|'ve)? ?(?:reached|hit|exceeded).{0,40}limit"],
    "antigravity": [r"rate.?limit", r"quota", r"resource.?exhausted", r"\b429\b",
                    r"too many requests", r"RESOURCE_EXHAUSTED", r"usage limit",
                    r"out of (?:credits|quota)"],
    "omlx": [r"out of memory", r"model not loaded", r"\b503\b",
             r"connection refused", r"overloaded"],
}
DEFAULT_RESET_HINTS = [r"try again in (\d+) ?(s|sec|seconds|m|min|minutes|h|hours)",
                       r"resets? in (\d+) ?(s|sec|seconds|m|min|minutes|h|hours)"]


def now() -> float:
    return time.time()


def load_policy():
    return _lib.load_config("fallback-policy.yaml") or {}


def _chains(policy):
    return (policy.get("chains") or DEFAULT_CHAINS)


def _agent_roles(policy):
    return (policy.get("agent_roles") or DEFAULT_AGENT_ROLES)


def _signals(policy):
    return ((policy.get("exhaustion") or {}).get("signals")) or DEFAULT_SIGNALS


def _cooldown(policy):
    return ((policy.get("exhaustion") or {}).get("default_cooldown_seconds")) or DEFAULT_COOLDOWN


def state_path():
    return os.path.join(_lib.runtime_dir(), "agent-usage.json")


def load_state():
    p = state_path()
    if os.path.exists(p):
        try:
            s = _lib.read_json(p)
        except Exception:
            s = {}
    else:
        s = {}
    s.setdefault("agents", {})
    s.setdefault("events", {})
    s["events"].setdefault("delegations", {})
    s["events"].setdefault("fallbacks", [])
    s["events"].setdefault("exhaustions", [])
    return s


def save_state(state):
    return _lib.write_json(state_path(), state)


# --------------------------------------------------------------------------- #
# Capabilities (installed-ness)
# --------------------------------------------------------------------------- #

def load_caps():
    """{codex, antigravity, omlx} installed flags from capabilities.json. Missing
    file -> optimistic (assume installed); exhaustion state is the real gate."""
    p = os.path.join(_lib.runtime_dir(), "capabilities.json")
    if not os.path.exists(p):
        return {"codex": True, "antigravity": True, "omlx": True}
    try:
        r = _lib.read_json(p)
    except Exception:
        return {"codex": True, "antigravity": True, "omlx": True}
    return {
        "codex": bool((r.get("codex") or {}).get("available")),
        "antigravity": bool((r.get("antigravity") or {}).get("available")),
        "omlx": bool((r.get("omlx") or {}).get("available")),
    }


def installed(agent, caps):
    if agent == "claude":
        return True
    return bool((caps or {}).get(agent, False))


# --------------------------------------------------------------------------- #
# Status + resolution
# --------------------------------------------------------------------------- #

def effective_status(agent, caps, state, now_ts=None):
    """available | exhausted | unavailable."""
    now_ts = now() if now_ts is None else now_ts
    if agent == "claude":
        return "available"
    if not installed(agent, caps):
        return "unavailable"
    a = (state.get("agents") or {}).get(agent) or {}
    if a.get("status") == "exhausted" and float(a.get("cooldown_until", 0)) > now_ts:
        return "exhausted"
    return "available"


def usable(agent, caps, state, now_ts=None):
    return effective_status(agent, caps, state, now_ts) == "available"


def resolve(preferred_agent, caps, state, policy=None, now_ts=None):
    """Walk the preferred agent's role chain from its own position to the first
    usable agent; Claude is the guaranteed final fallback. Returns
    (agent, hops) where hops lists the skipped agents and why."""
    policy = policy if policy is not None else load_policy()
    now_ts = now() if now_ts is None else now_ts
    role = _agent_roles(policy).get(preferred_agent, "research")
    chain = list(_chains(policy).get(role, ["claude"]))
    if preferred_agent in chain:
        chain = chain[chain.index(preferred_agent):]
    elif preferred_agent != "claude":
        chain = [preferred_agent] + chain
    hops = []
    for agent in chain:
        if agent == "claude":
            return "claude", hops
        st = effective_status(agent, caps, state, now_ts)
        if st == "available":
            return agent, hops
        hops.append({"agent": agent, "status": st})
    return "claude", hops


# --------------------------------------------------------------------------- #
# Exhaustion marking + detection
# --------------------------------------------------------------------------- #

def mark(state, agent, status, reason="", cooldown=None, now_ts=None, policy=None):
    policy = policy if policy is not None else load_policy()
    now_ts = now() if now_ts is None else now_ts
    entry = {"status": status, "reason": reason, "detected_at": _lib.now_iso()}
    if status == "exhausted":
        cd = cooldown if cooldown is not None else _cooldown(policy)
        entry["cooldown_until"] = now_ts + cd
        entry["cooldown_seconds"] = cd
        state["events"]["exhaustions"].append(
            {"agent": agent, "at": _lib.now_iso(), "reason": reason, "cooldown_seconds": cd})
    state.setdefault("agents", {})[agent] = entry
    return entry


def parse_reset_hint(text, policy=None):
    policy = policy if policy is not None else load_policy()
    pats = ((policy.get("exhaustion") or {}).get("reset_hint_patterns")) or DEFAULT_RESET_HINTS
    for pat in pats:
        m = re.search(pat, text or "", re.I)
        if m:
            n = int(m.group(1)); unit = m.group(2).lower()
            mult = 1 if unit.startswith("s") else 60 if unit.startswith("m") else 3600
            return n * mult
    return None


def detect_exhaustion(agent, text, policy=None):
    """Return (exhausted: bool, cooldown_seconds_or_None, matched_signal)."""
    policy = policy if policy is not None else load_policy()
    for pat in _signals(policy).get(agent, []):
        if re.search(pat, text or "", re.I):
            return True, parse_reset_hint(text, policy), pat
    return False, None, None


# --------------------------------------------------------------------------- #
# Accounting (token preservation)
# --------------------------------------------------------------------------- #

def record_delegation(state, agent):
    d = state["events"]["delegations"]
    d[agent] = d.get(agent, 0) + 1


def record_fallback(state, frm, to, reason=""):
    state["events"]["fallbacks"].append(
        {"from": frm, "to": to, "reason": reason, "at": _lib.now_iso()})


def report(state, policy=None):
    policy = policy if policy is not None else load_policy()
    est = ((policy.get("accounting") or {}).get("estimated_claude_tokens_per_delegation")) or 8000
    delegations = state["events"]["delegations"]
    total = sum(delegations.values())
    return {
        "delegations_by_agent": delegations,
        "total_delegations": total,
        "fallbacks": state["events"]["fallbacks"],
        "exhaustions": state["events"]["exhaustions"],
        "estimated_claude_tokens_preserved": total * est,
        "estimate_note": f"≈{est} tokens/delegation (heuristic); exact counts above are real.",
    }


# --------------------------------------------------------------------------- #

def _self_check():
    policy = {}  # use built-in defaults
    caps_all = {"codex": True, "antigravity": True, "omlx": True}
    t0 = 1_000_000.0
    s = {"agents": {}, "events": {"delegations": {}, "fallbacks": [], "exhaustions": []}}

    # all usable -> preferred wins
    assert resolve("antigravity", caps_all, s, policy, t0)[0] == "antigravity"
    assert resolve("codex", caps_all, s, policy, t0)[0] == "codex"
    assert resolve("omlx", caps_all, s, policy, t0)[0] == "omlx"

    # antigravity exhausted -> codex backup
    mark(s, "antigravity", "exhausted", "rate limit", cooldown=3600, now_ts=t0, policy=policy)
    a, hops = resolve("antigravity", caps_all, s, policy, t0)
    assert a == "codex" and hops[0]["agent"] == "antigravity" and hops[0]["status"] == "exhausted", (a, hops)

    # omlx unavailable (not installed) -> antigravity; but antigravity exhausted -> codex
    caps_no_omlx = {"codex": True, "antigravity": True, "omlx": False}
    a, _ = resolve("omlx", caps_no_omlx, s, policy, t0)
    assert a == "codex", a   # omlx down -> agy (exhausted) -> codex

    # everything out -> claude takes over
    mark(s, "codex", "exhausted", "quota", cooldown=3600, now_ts=t0, policy=policy)
    assert resolve("antigravity", caps_no_omlx, s, policy, t0)[0] == "claude"
    assert resolve("omlx", caps_no_omlx, s, policy, t0)[0] == "claude"
    assert resolve("codex", caps_no_omlx, s, policy, t0)[0] == "claude"

    # cooldown expiry -> agent usable again
    assert effective_status("antigravity", caps_all, s, t0 + 100) == "exhausted"
    assert effective_status("antigravity", caps_all, s, t0 + 4000) == "available"
    assert resolve("antigravity", caps_all, s, policy, t0 + 4000)[0] == "antigravity"

    # detection
    ex, cd, _ = detect_exhaustion("codex", "Error: you have reached your usage limit for today", policy)
    assert ex, "should detect codex exhaustion"
    ex, _, _ = detect_exhaustion("antigravity", "RESOURCE_EXHAUSTED: quota exceeded", policy)
    assert ex
    ex, _, _ = detect_exhaustion("codex", "normal successful output", policy)
    assert not ex
    # reset hint shortens cooldown
    assert parse_reset_hint("rate limit, try again in 15 minutes", policy) == 900

    # accounting
    record_delegation(s, "codex"); record_delegation(s, "codex"); record_delegation(s, "antigravity")
    r = report(s, policy)
    assert r["total_delegations"] == 3 and r["delegations_by_agent"]["codex"] == 2
    assert r["estimated_claude_tokens_preserved"] == 3 * 8000
    print("OK usage_lib self-check passed")


if __name__ == "__main__":
    _self_check()
