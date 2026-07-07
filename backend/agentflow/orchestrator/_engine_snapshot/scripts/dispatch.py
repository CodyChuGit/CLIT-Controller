#!/usr/bin/env python3
"""dispatch.py - turn a routing decision into concrete plugin invocations.

route-task.py decides WHO handles a stage (agent + persona). This decides HOW it
runs, given which plugins/CLIs are installed. v2 role model: Codex = local truth
+ control (deterministic ops run under the Codex lane); Antigravity (Gemini) =
eyes + web + narrative.

  codex stage   -> deterministic local script for ops (qa/git workflow/Apple -
                   running pytest/git/simctl needs no agent), or the
                   codex:codex-rescue subagent / /codex:review for semantic work
                   (analysis, review, synthesis, writing); raw codex-run.sh if
                   the plugin is absent; Claude absorbs it if Codex is gone.
  antigravity   -> agy:runner subagent / /agy:delegate for agentic work (browser
                   QA, visual analysis, live research); the diff-summary script
                   (deterministic gather + agy Flash writes) for the commit
                   narrative; raw agy -p if the plugin is absent.
  omlx          -> omlx-monitor.py, or Codex's operational takeover when oMLX is
                   off (codex-monitor.sh), or the bare supervisor.
  claude        -> handled inline.

Plugins targeted: codex@openai-codex, agy@antigravity-cc.

Usage:
  scripts/route-task.py --task-type FRONTEND_BUG_FIX | scripts/dispatch.py
  scripts/dispatch.py --decision-file d.json --caps runtime/capabilities.json
  scripts/dispatch.py --self-check
"""
from __future__ import annotations

import argparse
import json
import os
import sys


import _lib

DEFAULT_POLICY = {
    "mode": "prefer_plugin",
    "codex": {
        "subagent": "codex:codex-rescue",
        "commands": {"task": "/codex:rescue", "review": "/codex:review",
                     "adversarial_review": "/codex:adversarial-review"},
        "cli_fallback": "scripts/codex-run.sh",
        # Codex never writes FEATURE code (Claude implements); xcode-controller
        # may edit Apple project CONTAINERS only (pbxproj/schemes/xcconfig/plists).
        "write_personas": ["xcode-controller"],
        "review_personas": ["independent-reviewer"],
        "task_type_scripts": {
            "TEST_EXECUTION": "scripts/codex-qa.sh", "BUILD_EXECUTION": "scripts/codex-qa.sh",
            "LINT_EXECUTION": "scripts/codex-qa.sh", "FORMAT_CHECK": "scripts/codex-qa.sh",
            "STATIC_ANALYSIS": "scripts/codex-qa.sh", "QA_EVIDENCE_COLLECTION": "scripts/codex-qa.sh",
            "QA_REPORTING": "scripts/codex-qa.sh", "TASK_EXECUTION": "scripts/codex-task.sh",
            "RUNTIME_VALIDATION": "scripts/codex-runtime-check.sh",
            "LOCAL_FILE_DISCOVERY": "scripts/codex-browse.sh",
            "LOCAL_REPOSITORY_INVENTORY": "scripts/codex-browse.sh",
            "LOCAL_SYMBOL_SEARCH": "scripts/codex-browse.sh",
            "LOCAL_CONFIGURATION_DISCOVERY": "scripts/codex-browse.sh",
            "LOCAL_DEPENDENCY_INVENTORY": "scripts/codex-browse.sh",
            "TEST_DISCOVERY": "scripts/codex-browse.sh",
            "GIT_STATUS_INSPECTION": "scripts/codex-git-workflow.sh",
            "GIT_DIFF_INSPECTION": "scripts/codex-git-workflow.sh",
            "GIT_CHECKPOINT": "scripts/codex-git-workflow.sh",
            "GIT_COMMIT": "scripts/codex-git-workflow.sh",
            "GIT_PUSH": "scripts/codex-git-workflow.sh",
            "GIT_MILESTONE": "scripts/codex-git-workflow.sh",
            "GITHUB_VERSION_CONTROL": "scripts/codex-github.sh",
            "CI_MONITORING": "scripts/codex-ci-watch.sh",
            "XCODE_PROJECT_SETUP": "scripts/codex-apple.sh",
            "APPLE_BUILD_TEST": "scripts/codex-apple.sh",
            "SIMULATOR_LIFECYCLE": "scripts/codex-apple.sh",
            "APPLE_VERIFICATION": "scripts/codex-apple.sh",
            "LOG_TRIAGE": "scripts/codex-monitor.sh",
        },
        "deterministic_personas": {
            "qa-runner": "scripts/codex-qa.sh",
            "qa-reporter": "scripts/codex-qa.sh",
            "task-runner": "scripts/codex-task.sh",
            "git-steward": "scripts/codex-git-workflow.sh",
            "runtime-validator": "scripts/codex-runtime-check.sh",
            "repository-navigator": "scripts/codex-browse.sh",
            "xcode-controller": "scripts/codex-apple.sh",
        },
        "model": "gpt-5.5",     # Codex always at its best
        "effort": "xhigh",
    },
    "antigravity": {
        "subagent": "agy:runner",
        "commands": {"delegate": "/agy:delegate", "research": "/agy:research", "review": "/agy:review", "image": "/agy:image"},
        "cli_fallback": "scripts/antigravity-run.sh",
        "task_type_scripts": {
            "GIT_DIFF_SUMMARY": "scripts/antigravity-diff-summary.sh",
            "COMMIT_SUMMARY": "scripts/antigravity-diff-summary.sh",
            "MILESTONE_SUMMARY": "scripts/antigravity-diff-summary.sh",
            "FRONTEND_BROWSER_QA": "scripts/antigravity-browser-qa.sh",
        },
        "deterministic_personas": {
            "routine-tool-operator": "scripts/antigravity-run.sh",
            "commit-summarizer": "scripts/antigravity-diff-summary.sh",
        },
        "agentic_personas": {
            "browser-qa-operator": "scripts/antigravity-browser-qa.sh",
            "frontend-visual-reviewer": "scripts/antigravity-run.sh",
            "simulator-qa-analyst": "scripts/antigravity-run.sh",
            "web-researcher": "scripts/antigravity-run.sh",
            "github-scout": "scripts/antigravity-run.sh",
            "github-code-investigator": "scripts/antigravity-run.sh",
            "api-documentation-specialist": "scripts/antigravity-run.sh",
            "dependency-auditor": "scripts/antigravity-run.sh",
        },
        "agy_model": {
            "simple": "flash", "complex": "pro",
            "simple_task_types": [
                "ROUTINE_TOOL_CALL", "GIT_DIFF_SUMMARY", "COMMIT_SUMMARY",
                "MILESTONE_SUMMARY", "IMAGE_ASSET_GENERATION",
                "FRONTEND_BROWSER_QA", "FRONTEND_VISUAL_REVIEW",
                "SIMULATOR_VISUAL_QA",
            ],
            "simple_personas": ["routine-tool-operator", "commit-summarizer",
                                "browser-qa-operator", "frontend-visual-reviewer",
                                "simulator-qa-analyst"],
        },
        "agy_backed_task_types": ["GIT_DIFF_SUMMARY", "COMMIT_SUMMARY", "MILESTONE_SUMMARY"],
        "command_task_types": {"IMAGE_ASSET_GENERATION": "image"},
    },
    "omlx": {
        "monitor_script": "scripts/omlx-monitor.py",
        "takeover_script": "scripts/codex-monitor.sh",
        "supervisor": "scripts/job-supervisor.py",
    },
}


def load_policy():
    pol = _lib.load_config("dispatch-policy.yaml") or {}
    # shallow-merge over defaults so a partial/edited file still works
    merged = json.loads(json.dumps(DEFAULT_POLICY))
    for k, v in pol.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k].update(v)
        else:
            merged[k] = v
    return merged


def normalize_caps(report):
    """Map a detect-capabilities report -> the flat flags dispatch needs."""
    report = report or {}
    plugins = report.get("plugins") or {}
    return {
        "codex_cli": bool((report.get("codex") or {}).get("available")),
        "agy_cli": bool((report.get("antigravity") or {}).get("available")),
        "codex_plugin": bool(plugins.get("codex")),
        "agy_plugin": bool(plugins.get("agy")),
        "omlx": bool((report.get("omlx") or {}).get("available")),
    }


def agy_model(task_type, persona, policy):
    """Gemini 3.5 Flash (High) is the default worker: browser QA, visual
    analysis, OCR, simulator QA, and the commit narrative (Flash is explicitly
    assigned by spec). Pro-class only for deep/complex research."""
    am = (policy.get("antigravity") or {}).get("agy_model") or {}
    simple = (task_type in (am.get("simple_task_types") or [])
              or persona in (am.get("simple_personas") or []))
    return am.get("simple", "flash") if simple else am.get("complex", "pro")


def resolve_stage(stage, caps, policy, task_type=None):
    agent = stage.get("agent")
    persona = stage.get("persona")
    action = stage.get("action", "")
    mode = policy.get("mode", "prefer_plugin")
    base = {"agent": agent, "persona": persona, "action": action}

    if agent == "claude":
        return {**base, "via": "claude", "mechanism": "inline"}

    if agent == "codex":
        cp = policy["codex"]
        tts = cp.get("task_type_scripts") or {}
        det = cp.get("deterministic_personas") or {}
        # Deterministic local ops first: running pytest/git/simctl needs no
        # agent - the scripts return schema-conformant results under the Codex
        # lane (Codex owns local truth; the wrappers ARE its hands).
        if task_type and task_type in tts:
            return {**base, "via": "local_script", "mechanism": "script", "script": tts[task_type],
                    "note": "deterministic local op (by task type); Codex lane, no agent needed"}
        if persona in det:
            return {**base, "via": "local_script", "mechanism": "script", "script": det[persona],
                    "note": "deterministic local op; Codex lane, no agent needed"}
        use_plugin = mode != "cli_only" and (caps.get("codex_plugin") or mode == "plugin_only")
        if use_plugin:
            if persona in (cp.get("review_personas") or []):
                return {**base, "via": "codex_plugin", "mechanism": "slash_command",
                        "command": cp["commands"]["review"], "model": "configured-default",
                        "note": "native review-only reviewer (no --model flag; uses codex's "
                                "configured best model gpt-5.5/xhigh); returns review verbatim"}
            return {**base, "via": "codex_plugin", "mechanism": "subagent",
                    "subagent_type": cp["subagent"], "command_hint": cp["commands"]["task"],
                    "write": persona in (cp.get("write_personas") or []),
                    "model": cp.get("model") or "gpt-5.5", "effort": cp.get("effort") or "xhigh",
                    "prompt_source": "delegated task manifest (templates/base-task.md), redacted"}
        if caps.get("codex_cli"):
            return {**base, "via": "codex_cli", "mechanism": "script", "script": cp["cli_fallback"],
                    "model": cp.get("model") or "gpt-5.5", "effort": cp.get("effort") or "xhigh",
                    "note": "plugin unavailable; raw codex exec fallback (dry-run by default)"}
        return {**base, "via": "degraded", "mechanism": "claude_fallback",
                "note": "Codex unavailable; Claude absorbs analysis/review/ops (costlier; "
                        "QA/Git safety gates still apply)."}

    if agent == "antigravity":
        ap = policy["antigravity"]
        tts = ap.get("task_type_scripts") or {}
        det = ap.get("deterministic_personas") or {}
        agc = ap.get("agentic_personas") or {}
        # Task types that map to a dedicated agy plugin command (e.g. image
        # generation via agy's built-in generate_image / Imagen).
        ctt = ap.get("command_task_types") or {}
        if task_type and task_type in ctt:
            cmd = (ap.get("commands") or {}).get(ctt[task_type], "/agy:" + ctt[task_type])
            m = agy_model(task_type, persona, policy)
            if mode != "cli_only" and (caps.get("agy_plugin") or mode == "plugin_only"):
                return {**base, "via": "agy_plugin", "mechanism": "slash_command", "command": cmd,
                        "model": m, "agy_model": m,
                        "note": "agy built-in capability (generate_image / Imagen)"}
            if caps.get("agy_cli"):
                return {**base, "via": "agy_cli", "mechanism": "script",
                        "script": ap["cli_fallback"], "model": m, "agy_model": m,
                        "note": "plugin absent; raw agy -p with the generation prompt"}
            return {**base, "via": "degraded", "mechanism": "claude_minimal_fallback",
                    "note": "agy unavailable; image generation cannot be faked - report honestly."}
        # Tier the agy model once: Flash is the default worker; Pro for deep research.
        model = agy_model(task_type, persona, policy)
        base = {**base, "agy_model": model}
        # most precise: concrete TASK_TYPE -> local script (the commit narrative:
        # deterministic gather, then agy Flash WRITES the prose)
        if task_type and task_type in tts:
            agy_backed = task_type in (ap.get("agy_backed_task_types") or [])
            if agy_backed:
                return {**base, "via": "local_script", "mechanism": "script", "script": tts[task_type],
                        "uses_agy": True, "model": model,
                        "note": f"gathers git evidence deterministically, then agy writes the summary (model: {model})"}
            return {**base, "via": "local_script", "mechanism": "script", "script": tts[task_type],
                    "note": "local wrapper (by task type)"}
        if persona in det:
            return {**base, "via": "local_script", "mechanism": "script", "script": det[persona],
                    "note": "deterministic local op; no agy agent needed"}
        if persona in agc:
            # truly agentic work (browser QA, visual analysis, live research):
            # prefer the agy:runner subagent; the mapped script is the raw fallback.
            if mode != "cli_only" and (caps.get("agy_plugin") or mode == "plugin_only"):
                return {**base, "via": "agy_plugin", "mechanism": "subagent",
                        "subagent_type": ap["subagent"], "command_hint": ap["commands"]["delegate"],
                        "model": model, "script_fallback": agc[persona]}
            if caps.get("agy_cli"):
                return {**base, "via": "agy_cli", "mechanism": "script", "script": agc[persona],
                        "model": model, "note": "plugin unavailable; local wrapper / raw agy -p"}
            return {**base, "via": "degraded", "mechanism": "claude_minimal_fallback",
                    "note": "Antigravity unavailable; visual/live-web observation cannot be "
                            "faked - Codex verifies locally, Claude decides with what exists."}
        if mode != "cli_only" and (caps.get("agy_plugin") or mode == "plugin_only"):
            return {**base, "via": "agy_plugin", "mechanism": "subagent",
                    "subagent_type": ap["subagent"], "command_hint": ap["commands"]["delegate"],
                    "model": model}
        if caps.get("agy_cli"):
            return {**base, "via": "agy_cli", "mechanism": "script", "script": ap["cli_fallback"],
                    "model": model, "note": "plugin unavailable; raw `agy -p` (model via plugin only)"}
        return {**base, "via": "degraded", "mechanism": "claude_minimal_fallback",
                "note": "Antigravity unavailable; Claude runs minimal local fallback. QA/Git gates still apply."}

    if agent == "omlx":
        op = policy["omlx"]
        ap = policy["antigravity"]
        # _monitor_target is set by dispatch_plan from live usage (omlx ->
        # codex -> antigravity -> supervisor). On a direct call (tests) derive it
        # from installed caps so behaviour is unchanged without usage state.
        target = stage.get("_monitor_target")
        if target is None:
            if caps.get("omlx"):
                target = "omlx"
            elif caps.get("codex_plugin") or caps.get("codex_cli"):
                target = "codex"
            elif caps.get("agy_plugin") or caps.get("agy_cli"):
                target = "antigravity"
            else:
                target = "supervisor"
        if target == "omlx":
            return {**base, "via": "omlx", "mechanism": "script", "script": op["monitor_script"]}
        if target == "codex":
            return {**base, "via": "codex_takeover", "mechanism": "script",
                    "script": op["takeover_script"],
                    "note": "oMLX not loaded/exhausted; Codex operational (grep-based) triage "
                            "(it owns heartbeat supervision)."}
        if target == "antigravity":
            return {**base, "via": "agy_takeover", "mechanism": "subagent",
                    "subagent_type": ap["subagent"], "model": "flash",
                    "note": "oMLX + Codex out; agy (Flash) summarizes the job logs "
                            "(advisory; supervisor stays Level 0)."}
        return {**base, "via": "deterministic_supervisor", "mechanism": "script",
                "script": op["supervisor"],
                "note": "all monitors out; bare deterministic supervisor; Claude reviews."}

    return {**base, "via": "unknown", "mechanism": "none"}


def dispatch_plan(decision, caps, policy=None, usage_state=None):
    """Resolve each routed stage to a concrete invocation. Before picking the
    mechanism, each stage is routed to the EFFECTIVE agent: if the preferred
    agent is exhausted (out of usage) or uninstalled, usage_lib walks the
    fallback chain (codex<->agy, omlx->codex->agy, all-out->claude). This is
    what spreads load across agents/accounts and preserves Claude tokens."""
    policy = policy or load_policy()
    import usage_lib as U
    upolicy = U.load_policy()
    state = usage_state if usage_state is not None else U.load_state()
    installed = {
        "codex": bool(caps.get("codex_cli") or caps.get("codex_plugin")),
        "antigravity": bool(caps.get("agy_cli") or caps.get("agy_plugin")),
        "omlx": bool(caps.get("omlx")),
    }
    task_type = decision.get("task_type")
    stages = decision.get("stages") or [{"agent": decision.get("primary_agent"),
                                         "persona": decision.get("persona"), "action": ""}]
    plan, usage_fallbacks = [], []
    for s in stages:
        # oMLX monitoring fallback uses monitoring-specific mechanisms, not the
        # generic agent reroute: omlx -> codex grep-triage -> agy log summary ->
        # bare supervisor. Compute the target, keep the omlx branch in charge.
        if s.get("agent") == "omlx":
            mon, hops = U.resolve("omlx", installed, state, upolicy)
            stage = dict(s)
            stage["_monitor_target"] = "supervisor" if mon == "claude" else mon
            entry = resolve_stage(stage, caps, policy, task_type=task_type)
            if mon != "omlx":
                entry["fallback_from"] = "omlx"
                entry["fallback_reason"] = "; ".join(f"{h['agent']}:{h['status']}" for h in hops)
                usage_fallbacks.append({"from": "omlx", "to": mon})
            plan.append(entry)
            continue
        eff, hops = U.resolve(s.get("agent"), installed, state, upolicy)
        stage = dict(s)
        fellback = eff != s.get("agent")
        if fellback:
            reason = "; ".join(f"{h['agent']}:{h['status']}" for h in hops)
            stage = {"agent": eff, "persona": None, "action": s.get("action", "")}
            usage_fallbacks.append({"from": s.get("agent"), "to": eff, "reason": reason})
        entry = resolve_stage(stage, caps, policy, task_type=task_type)
        if fellback:
            entry["fallback_from"] = s.get("agent")
            entry["fallback_reason"] = reason
            entry["preferred_persona"] = s.get("persona")
        plan.append(entry)
    result = {
        "task_id": decision.get("task_id"),
        "task_type": decision.get("task_type"),
        "decision": decision.get("decision"),
        "mode": policy.get("mode", "prefer_plugin"),
        "capabilities": caps,
        "dispatch": plan,
    }
    if usage_fallbacks:
        result["usage_fallbacks"] = usage_fallbacks
    return result


def _self_check():
    pol = load_policy()
    plug = {"codex_cli": True, "agy_cli": True, "codex_plugin": True, "agy_plugin": True, "omlx": False}
    nocli = {"codex_cli": False, "agy_cli": False, "codex_plugin": False, "agy_plugin": False, "omlx": False}

    # codex semantic analysis -> subagent codex:codex-rescue (read-only), best model + xhigh
    d = resolve_stage({"agent": "codex", "persona": "codebase-analyst"}, plug, pol)
    assert d["via"] == "codex_plugin" and d["subagent_type"] == "codex:codex-rescue" and d["write"] is False, d
    assert d["model"] == "gpt-5.5" and d["effort"] == "xhigh", d
    # codex xcode-controller may write (project CONTAINERS only)
    d = resolve_stage({"agent": "codex", "persona": "xcode-controller"}, plug, pol, task_type="XCODE_PROJECT_SETUP")
    assert d["via"] == "local_script" and d["script"].endswith("codex-apple.sh"), d
    # codex independent review -> /codex:review slash command
    d = resolve_stage({"agent": "codex", "persona": "independent-reviewer"}, plug, pol)
    assert d["mechanism"] == "slash_command" and d["command"] == "/codex:review", d
    # codex plugin absent but CLI present -> raw fallback script
    d = resolve_stage({"agent": "codex", "persona": "codebase-analyst"},
                      {"codex_cli": True, "codex_plugin": False}, pol)
    assert d["via"] == "codex_cli" and d["script"].endswith("codex-run.sh"), d
    # codex fully absent -> Claude absorbs
    d = resolve_stage({"agent": "codex", "persona": "codebase-analyst"}, nocli, pol)
    assert d["via"] == "degraded", d

    # codex qa-runner -> deterministic local script (no agent) under the Codex lane
    d = resolve_stage({"agent": "codex", "persona": "qa-runner"}, plug, pol)
    assert d["via"] == "local_script" and d["script"].endswith("codex-qa.sh"), d
    # codex git-steward -> git workflow script
    d = resolve_stage({"agent": "codex", "persona": "git-steward"}, plug, pol)
    assert d["script"].endswith("codex-git-workflow.sh"), d
    # git-steward + GIT_MILESTONE -> git workflow script
    d = resolve_stage({"agent": "codex", "persona": "git-steward"}, plug, pol, task_type="GIT_MILESTONE")
    assert d["script"].endswith("codex-git-workflow.sh"), d
    # git-steward + GITHUB_VERSION_CONTROL -> github script
    d = resolve_stage({"agent": "codex", "persona": "git-steward"}, plug, pol, task_type="GITHUB_VERSION_CONTROL")
    assert d["script"].endswith("codex-github.sh"), d
    # task-runner + TASK_EXECUTION -> task script
    d = resolve_stage({"agent": "codex", "persona": "task-runner"}, plug, pol, task_type="TASK_EXECUTION")
    assert d["script"].endswith("codex-task.sh"), d
    # Apple: xcode-controller + APPLE_BUILD_TEST -> apple script
    d = resolve_stage({"agent": "codex", "persona": "xcode-controller"}, plug, pol, task_type="APPLE_BUILD_TEST")
    assert d["script"].endswith("codex-apple.sh"), d

    # agy commit narrative: commit-summarizer + COMMIT_SUMMARY -> diff-summary
    # script, agy-backed (Flash writes the prose)
    d = resolve_stage({"agent": "antigravity", "persona": "commit-summarizer"}, plug, pol, task_type="COMMIT_SUMMARY")
    assert d["script"].endswith("antigravity-diff-summary.sh"), d
    assert d.get("uses_agy") is True and d["model"] == "flash" and d["agy_model"] == "flash", d
    d = resolve_stage({"agent": "antigravity", "persona": "commit-summarizer"}, plug, pol, task_type="MILESTONE_SUMMARY")
    assert d.get("uses_agy") is True and d["model"] == "flash", d
    # browser QA -> agy:runner subagent preferred (Flash default), script fallback recorded
    d = resolve_stage({"agent": "antigravity", "persona": "browser-qa-operator"}, plug, pol)
    assert d["via"] == "agy_plugin" and d["subagent_type"] == "agy:runner", d
    assert d["model"] == "flash" and d["script_fallback"].endswith("antigravity-browser-qa.sh"), d
    # simulator visual QA -> agy:runner, Flash
    d = resolve_stage({"agent": "antigravity", "persona": "simulator-qa-analyst"}, plug, pol, task_type="SIMULATOR_VISUAL_QA")
    assert d["via"] == "agy_plugin" and d["model"] == "flash", d
    # live research -> agy:runner, Pro (deep research)
    d = resolve_stage({"agent": "antigravity", "persona": "web-researcher"}, plug, pol, task_type="WEB_RESEARCH")
    assert d["via"] == "agy_plugin" and d["model"] == "pro", d
    # generic agentic antigravity (unknown persona) -> agy:runner, complex -> pro
    d = resolve_stage({"agent": "antigravity", "persona": "explorer"}, plug, pol)
    assert d["via"] == "agy_plugin" and d["subagent_type"] == "agy:runner" and d["model"] == "pro", d

    # agy model tiers: Flash is the default worker; Pro for deep research
    assert agy_model("COMMIT_SUMMARY", "x", pol) == "flash"
    assert agy_model("GIT_DIFF_SUMMARY", "x", pol) == "flash"
    assert agy_model("FRONTEND_BROWSER_QA", "browser-qa-operator", pol) == "flash"
    assert agy_model("SIMULATOR_VISUAL_QA", "simulator-qa-analyst", pol) == "flash"
    assert agy_model(None, "commit-summarizer", pol) == "flash"
    assert agy_model("WEB_RESEARCH", "web-researcher", pol) == "pro"
    assert agy_model("PARALLEL_INVESTIGATION", "explorer", pol) == "pro"
    # agy plugin absent but cli present -> local wrapper / raw agy fallback
    d = resolve_stage({"agent": "antigravity", "persona": "web-researcher"},
                      {"agy_cli": True, "agy_plugin": False}, pol)
    assert d["via"] == "agy_cli", d

    # image generation -> agy's /agy:image (built-in Imagen), flash tier
    d = resolve_stage({"agent": "antigravity", "persona": "routine-tool-operator"}, plug, pol,
                      task_type="IMAGE_ASSET_GENERATION")
    assert d["via"] == "agy_plugin" and d["command"] == "/agy:image" and d["model"] == "flash", d

    # omlx off but codex present -> Codex takeover (it owns heartbeat supervision)
    d = resolve_stage({"agent": "omlx", "persona": None}, plug, pol)
    assert d["via"] == "codex_takeover" and d["script"].endswith("codex-monitor.sh"), d
    # omlx + codex off, agy present -> agy log summary
    d = resolve_stage({"agent": "omlx", "persona": None},
                      {"agy_cli": True, "agy_plugin": True}, pol)
    assert d["via"] == "agy_takeover", d
    # everything off -> bare supervisor
    d = resolve_stage({"agent": "omlx", "persona": None}, nocli, pol)
    assert d["via"] == "deterministic_supervisor", d

    # cli_only mode never uses plugins
    pol2 = dict(pol, mode="cli_only")
    d = resolve_stage({"agent": "codex", "persona": "codebase-analyst"}, plug, pol2)
    assert d["via"] == "codex_cli", d

    # full plan over the v2 frontend loop: agy reproduce -> Claude fix ->
    # Codex regression -> agy visual confirm -> Codex change-unit commit
    decision = {"task_id": "t", "task_type": "MIXED_FRONTEND_QA_AND_FIX",
                "decision": "FRONTEND_QA_FIX_LOOP",
                "stages": [{"agent": "antigravity", "persona": "browser-qa-operator"},
                           {"agent": "claude", "persona": "principal-engineer"},
                           {"agent": "codex", "persona": "qa-runner"},
                           {"agent": "antigravity", "persona": "frontend-visual-reviewer"},
                           {"agent": "codex", "persona": "git-steward"}]}
    NOEX = {"agents": {}}  # hermetic: no exhaustion
    plan = dispatch_plan(decision, plug, pol, usage_state=NOEX)
    vias = [s["via"] for s in plan["dispatch"]]
    assert vias == ["agy_plugin", "claude", "local_script", "agy_plugin", "local_script"], vias

    # usage fallback: agy exhausted -> a research stage falls to codex
    t0 = 1_000_000.0
    exhausted = {"agents": {"antigravity": {"status": "exhausted", "cooldown_until": t0 + 9_000}}}
    rdecision = {"task_id": "t", "task_type": "WEB_RESEARCH", "decision": "DELEGATE_TO_ANTIGRAVITY",
                 "stages": [{"agent": "antigravity", "persona": "web-researcher"}]}
    import usage_lib as U
    _orig = U.now
    U.now = lambda: t0
    try:
        p2 = dispatch_plan(rdecision, plug, pol, usage_state=exhausted)
    finally:
        U.now = _orig
    d0 = p2["dispatch"][0]
    assert d0["agent"] == "codex" and d0["via"] == "codex_plugin", d0
    assert d0["fallback_from"] == "antigravity" and p2["usage_fallbacks"][0]["to"] == "codex", p2
    print("OK dispatch self-check passed")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Resolve a routing decision into plugin invocations.")
    ap.add_argument("--decision-file", help="routing-decision JSON (default: stdin)")
    ap.add_argument("--caps", help="capabilities.json (default: runtime cache, else detect-less assume all CLI)")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args(argv)
    if args.self_check:
        _self_check()
        return 0

    raw = open(args.decision_file, encoding="utf-8").read() if args.decision_file else sys.stdin.read()
    decision = json.loads(raw)
    caps_path = args.caps or os.path.join(_lib.runtime_dir(), "capabilities.json")
    report = _lib.read_json(caps_path) if os.path.exists(caps_path) else {}
    caps = normalize_caps(report)
    print(json.dumps(dispatch_plan(decision, caps), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
