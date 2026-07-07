#!/usr/bin/env python3
"""route-task.py - deterministic task router for the agent orchestrator.

Maps a unit of work to a routing decision (which agent(s), in what order, with
what persona, and whether to attach an oMLX monitor). The authoritative
TASK_TYPE -> decision table lives here so routing always works even if
config/routing-policy.yaml is missing or invalid; the YAML layers tunables,
per-type overrides, and extra intent hints on top.

Role model (v2, spec-aligned):
  Claude  builds — architecture, all implementation (frontend + Swift included),
          debugging, final judgment.
  Codex   controls and verifies locally — files, repo, shell, tests, git
          workflow execution, Xcode/simulators, heartbeat supervision.
  Antigravity (Gemini) looks, searches, repeats — browser QA, visual judgment,
          OCR/vision, live web research, commit/milestone narrative.
  oMLX    optional cheap log triage for long-running jobs.

Usage:
  route-task.py --task-type TEST_EXECUTION
  route-task.py --text "trace how auth flows through the backend"
  route-task.py --task-type BUILD_EXECUTION --long-running --task-id job-42
  echo "research the current playwright api" | route-task.py
  route-task.py --self-check

Output: a routing-decision.schema.json object as JSON on stdout.
"""
from __future__ import annotations

import argparse
import json
import sys

import _lib

CLAUDE = "claude"
CODEX = "codex"
ANTI = "antigravity"
OMLX = "omlx"

# task_type -> (decision, primary_agent, persona, rationale)
ROUTE_TABLE = {
    # ---- Claude: architecture / implementation / judgment ------------------
    "LOCAL_CORE_IMPLEMENTATION": ("HANDLE_WITH_CLAUDE", CLAUDE, "principal-engineer", "Core implementation is Claude's authority."),
    "LOCAL_BACKEND_IMPLEMENTATION": ("HANDLE_WITH_CLAUDE", CLAUDE, "principal-engineer", "Backend services, persistence and contracts stay with Claude."),
    "LOCAL_FRONTEND_IMPLEMENTATION": ("HANDLE_WITH_CLAUDE", CLAUDE, "principal-engineer", "Claude writes all frontend code (agy runs browser QA; Codex verifies locally)."),
    "LOCAL_DEBUGGING": ("HANDLE_WITH_CLAUDE", CLAUDE, "principal-engineer", "Root-cause debugging is Claude's job (Codex may gather local truth first)."),
    "LOCAL_CODE_REVIEW": ("HANDLE_WITH_CLAUDE", CLAUDE, "principal-engineer", "Final acceptance review is Claude's; independent review delegates to Codex."),
    "LOCAL_ARCHITECTURE": ("HANDLE_WITH_CLAUDE", CLAUDE, "principal-engineer", "Architecture and system boundaries are Claude's authority."),
    "FRONTEND_BUG_FIX": ("HANDLE_WITH_CLAUDE", CLAUDE, "principal-engineer", "Claude fixes frontend code; agy reproduces + judges visuals; Codex verifies + commits."),
    "DO_NOT_DELEGATE": ("HANDLE_WITH_CLAUDE", CLAUDE, "principal-engineer", "Explicitly retained by Claude."),
    # ---- Codex: local truth / repo intelligence / review / writing ---------
    "CODEBASE_SEMANTIC_ANALYSIS": ("DELEGATE_TO_CODEX", CODEX, "codebase-analyst", "Codex owns local truth: it explains the system."),
    "CODEBASE_ARCHITECTURE_MAPPING": ("DELEGATE_TO_CODEX", CODEX, "codebase-analyst", "Architecture mapping is semantic analysis -> Codex."),
    "CODEBASE_FLOW_TRACING": ("DELEGATE_TO_CODEX", CODEX, "codebase-analyst", "Flow tracing is semantic analysis -> Codex."),
    "BLAST_RADIUS_ANALYSIS": ("DELEGATE_TO_CODEX", CODEX, "codebase-analyst", "Blast-radius analysis is semantic analysis -> Codex."),
    "SPECIFICATION_CONSISTENCY_REVIEW": ("DELEGATE_TO_CODEX", CODEX, "independent-reviewer", "Spec-vs-code comparison -> Codex independent reviewer."),
    "RESEARCH_SYNTHESIS": ("DELEGATE_TO_CODEX", CODEX, "research-synthesizer", "Combining evidence into an implementation brief -> Codex (verifies against local repo)."),
    "PARALLEL_INVESTIGATION": ("DELEGATE_TO_CODEX", CODEX, "parallel-investigation-lead", "Parallel subagent investigation -> Codex; one synthesis returns."),
    "INDEPENDENT_IMPLEMENTATION_REVIEW": ("DELEGATE_TO_CODEX", CODEX, "independent-reviewer", "Independent PR-style review uses a fresh Codex reviewer."),
    "TEST_PLAN_DESIGN": ("DELEGATE_TO_CODEX", CODEX, "test-strategy-designer", "Test matrices designed and executed by Codex."),
    "MARKDOWN_AUTHORING": ("DELEGATE_TO_CODEX", CODEX, "technical-writer", "Substantial Markdown drafting -> Codex; Claude verifies truth."),
    "PROJECT_DOCUMENTATION": ("DELEGATE_TO_CODEX", CODEX, "technical-writer", "Project documentation -> Codex technical writer."),
    # ---- Codex: local files / operations / QA ------------------------------
    "LOCAL_FILE_DISCOVERY": ("DELEGATE_TO_CODEX", CODEX, "repository-navigator", "Local file access is Codex's lane."),
    "LOCAL_REPOSITORY_INVENTORY": ("DELEGATE_TO_CODEX", CODEX, "repository-navigator", "Repository inventory -> Codex."),
    "LOCAL_SYMBOL_SEARCH": ("DELEGATE_TO_CODEX", CODEX, "repository-navigator", "Symbol/text search -> Codex."),
    "LOCAL_CONFIGURATION_DISCOVERY": ("DELEGATE_TO_CODEX", CODEX, "repository-navigator", "Configuration discovery -> Codex."),
    "LOCAL_DEPENDENCY_INVENTORY": ("DELEGATE_TO_CODEX", CODEX, "repository-navigator", "Manifest/dependency inventory -> Codex."),
    "TEST_DISCOVERY": ("DELEGATE_TO_CODEX", CODEX, "repository-navigator", "Test discovery -> Codex."),
    "TEST_EXECUTION": ("DELEGATE_TO_CODEX", CODEX, "qa-runner", "Test execution -> Codex QA Runner (local truth)."),
    "BUILD_EXECUTION": ("DELEGATE_TO_CODEX", CODEX, "qa-runner", "Build execution -> Codex."),
    "LINT_EXECUTION": ("DELEGATE_TO_CODEX", CODEX, "qa-runner", "Lint -> Codex."),
    "FORMAT_CHECK": ("DELEGATE_TO_CODEX", CODEX, "qa-runner", "Format check -> Codex."),
    "STATIC_ANALYSIS": ("DELEGATE_TO_CODEX", CODEX, "qa-runner", "Static analysis -> Codex."),
    "RUNTIME_VALIDATION": ("DELEGATE_TO_CODEX", CODEX, "runtime-validator", "Runtime validation -> Codex."),
    "QA_EVIDENCE_COLLECTION": ("DELEGATE_TO_CODEX", CODEX, "qa-runner", "QA evidence collection -> Codex."),
    "QA_REPORTING": ("DELEGATE_TO_CODEX", CODEX, "qa-reporter", "Structured QA reporting -> Codex QA Reporter."),
    "TASK_EXECUTION": ("DELEGATE_TO_CODEX", CODEX, "task-runner", "Running project tasks/scripts -> Codex Task Runner."),
    # ---- Codex: git workflow execution + GitHub + CI -----------------------
    "GIT_STATUS_INSPECTION": ("DELEGATE_TO_CODEX", CODEX, "git-steward", "Git status -> Codex Git Steward."),
    "GIT_DIFF_INSPECTION": ("DELEGATE_TO_CODEX", CODEX, "git-steward", "Git diff -> Codex Git Steward."),
    "GIT_CHECKPOINT": ("DELEGATE_TO_CODEX", CODEX, "git-steward", "Change-unit commit loop (stage, agy-flash message, commit on staging surface) -> Codex per GIT_WORKFLOW."),
    "GIT_COMMIT": ("DELEGATE_TO_CODEX", CODEX, "git-steward", "Commit -> Codex (message written by agy Flash from the staged diff)."),
    "GIT_PUSH": ("DELEGATE_TO_CODEX", CODEX, "git-steward", "Push -> Codex; automatic to staging after a milestone, production only with explicit user confirmation."),
    "GIT_MILESTONE": ("DELEGATE_TO_CODEX", CODEX, "git-steward", "Milestone: collect range, agy-Flash milestone summary, annotated tag, automatic staging push."),
    "GITHUB_VERSION_CONTROL": ("DELEGATE_TO_CODEX", CODEX, "git-steward", "GitHub version control (PRs, branches, releases, tags via gh) -> Codex Git Steward."),
    "CI_MONITORING": ("DELEGATE_TO_CODEX", CODEX, "git-steward", "CI monitoring -> Codex."),
    # ---- Codex: Apple platform (Xcode + simulators) ------------------------
    "XCODE_PROJECT_SETUP": ("DELEGATE_TO_CODEX", CODEX, "xcode-controller", "Xcode project/workspace/target/scheme setup -> Codex, the sole Mac controller."),
    "SIMULATOR_LIFECYCLE": ("DELEGATE_TO_CODEX", CODEX, "xcode-controller", "simctl lifecycle (create/pair/boot/erase/shutdown/delete) -> Codex; simulators are disposable."),
    "APPLE_BUILD_TEST": ("CODEX_WITH_OMLX_MONITOR", CODEX, "xcode-controller", "xcodebuild build/test is long-running by definition -> Codex under a heartbeat."),
    "APPLE_VERIFICATION": ("CODEX_THEN_ANTIGRAVITY", CODEX, "xcode-controller", "Codex builds/tests/captures across the destination matrix; agy judges the screens; Claude decides."),
    # ---- Antigravity (Gemini): live web / research --------------------------
    "WEB_RESEARCH": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "web-researcher", "Live web research is Gemini's lane (Google-grounded), off Claude's clock."),
    "CURRENT_INFORMATION": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "web-researcher", "Current information must be fetched, dated, and sourced -> agy."),
    "GITHUB_REPOSITORY_SEARCH": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "github-scout", "Repo discovery + health -> agy live search."),
    "GITHUB_CODE_SEARCH": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "github-code-investigator", "Real-world implementation search -> agy."),
    "GITHUB_ISSUE_RESEARCH": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "github-code-investigator", "Issue/workaround research -> agy."),
    "API_DOCUMENTATION": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "api-documentation-specialist", "API/SDK documentation research -> agy."),
    "DEPENDENCY_EVALUATION": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "dependency-auditor", "Dependency comparison -> agy live research (Claude picks; Codex checks local fit)."),
    "TECHNOLOGY_COMPARISON": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "dependency-auditor", "Technology comparison -> agy live research."),
    # ---- Antigravity (Gemini): browser / visual / vision ---------------------
    "FRONTEND_BROWSER_QA": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "browser-qa-operator", "Browser operation and observation are Gemini's."),
    "FRONTEND_VISUAL_REVIEW": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "frontend-visual-reviewer", "Visual truth is Gemini's; Codex verifies local state before Claude acts on it."),
    "SIMULATOR_VISUAL_QA": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "simulator-qa-analyst", "Simulator screenshot/recording QA -> agy (Codex captures, Gemini analyzes)."),
    "IMAGE_ASSET_GENERATION": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "routine-tool-operator", "Image/asset generation -> agy's built-in generate_image (Imagen) via /agy:image."),
    "ROUTINE_TOOL_CALL": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "routine-tool-operator", "Routine repetitive tool calls / macros -> agy."),
    # ---- Antigravity (Gemini): commit narrative ------------------------------
    "GIT_DIFF_SUMMARY": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "commit-summarizer", "Diff summarization -> agy Flash writes the narrative from the diff."),
    "COMMIT_SUMMARY": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "commit-summarizer", "Per-commit message from the staged diff -> agy Flash (Haiku fallback; never blocks a commit)."),
    "MILESTONE_SUMMARY": ("DELEGATE_TO_ANTIGRAVITY", ANTI, "commit-summarizer", "Milestone summary from log + cumulative diff + validation results -> agy Flash."),
    # ---- oMLX + long-running -----------------------------------------------
    "LONG_RUNNING_JOB": ("CODEX_WITH_OMLX_MONITOR", CODEX, "qa-runner", "Codex runs the job under a supervisor; oMLX watches the logs."),
    "LOG_TRIAGE": ("DELEGATE_TO_OMLX_MONITOR", OMLX, None, "Log compression and triage -> cheap local oMLX observer."),
    # ---- Mixed: explicit staged pipelines ----------------------------------
    "MIXED_RESEARCH_AND_IMPLEMENTATION": ("RESEARCH_THEN_IMPLEMENT_THEN_VALIDATE", CLAUDE, None, "agy researches live, Codex synthesizes against the repo, Claude decides+implements, Codex validates."),
    "MIXED_FRONTEND_QA_AND_FIX": ("FRONTEND_QA_FIX_LOOP", CLAUDE, "principal-engineer", "agy reproduces + judges visuals, CLAUDE fixes, Codex regresses + commits."),
    "MIXED_CORE_CHANGE_AND_VALIDATION": ("CLAUDE_THEN_CODEX", CLAUDE, "principal-engineer", "Claude implements the core change, Codex validates and commits the change unit."),
}

SINGLE_AGENT = {"HANDLE_WITH_CLAUDE", "DELEGATE_TO_CODEX", "DELEGATE_TO_ANTIGRAVITY"}
MONITOR_UPGRADE = {
    "HANDLE_WITH_CLAUDE": "CLAUDE_WITH_OMLX_MONITOR",
    "DELEGATE_TO_CODEX": "CODEX_WITH_OMLX_MONITOR",
    "DELEGATE_TO_ANTIGRAVITY": "ANTIGRAVITY_WITH_OMLX_MONITOR",
}
MONITOR_DECISIONS = {
    "DELEGATE_TO_OMLX_MONITOR", "CLAUDE_WITH_OMLX_MONITOR", "CODEX_WITH_OMLX_MONITOR",
    "ANTIGRAVITY_WITH_OMLX_MONITOR",
}
# Task types that always run under a heartbeat, whatever the caller says
# (Apple builds + multi-destination verification are long-running by definition).
ALWAYS_MONITOR = {"APPLE_VERIFICATION"}

# Built-in intent hints (extended, never replaced, by routing-policy.yaml).
DEFAULT_INTENT_HINTS = {
    "LOCAL_ARCHITECTURE": ["architecture", "system boundary", "state machine", "data model", "design the system", "concurrency model"],
    "LOCAL_BACKEND_IMPLEMENTATION": ["backend", "server endpoint", "api endpoint", "migration", "database", "persistence"],
    "LOCAL_CORE_IMPLEMENTATION": ["implement the core", "core logic", "business logic"],
    "LOCAL_DEBUGGING": ["root cause", "debug", "why does it crash", "fix the bug"],
    "LOCAL_FRONTEND_IMPLEMENTATION": ["build the component", "new screen", "new page", "implement the ui"],
    "FRONTEND_BUG_FIX": ["css bug", "layout broken", "responsive issue", "button broken", "styling bug", "frontend bug"],
    "FRONTEND_VISUAL_REVIEW": ["visual review", "does it look right", "ux review", "design fidelity"],
    "CODEBASE_SEMANTIC_ANALYSIS": ["how does this work", "explain the codebase", "understand the system", "what does this module do"],
    "CODEBASE_FLOW_TRACING": ["trace the flow", "request flow", "data flow", "follow the call"],
    "BLAST_RADIUS_ANALYSIS": ["blast radius", "what breaks if", "impact of changing", "who calls"],
    "WEB_RESEARCH": ["research", "look up", "current best practice", "latest", "find documentation"],
    "CURRENT_INFORMATION": ["latest version", "as of now", "current state of"],
    "GITHUB_REPOSITORY_SEARCH": ["find a library", "which package", "best repo for"],
    "GITHUB_CODE_SEARCH": ["find an example", "real-world implementation", "how do others"],
    "API_DOCUMENTATION": ["api docs", "sdk documentation", "how to authenticate", "rate limits"],
    "DEPENDENCY_EVALUATION": ["compare packages", "evaluate dependency", "which dependency", "should we use"],
    "PARALLEL_INVESTIGATION": ["investigate in parallel", "deep investigation", "multi-angle"],
    "INDEPENDENT_IMPLEMENTATION_REVIEW": ["independent review", "review the diff", "review my implementation"],
    "TEST_PLAN_DESIGN": ["test plan", "test matrix", "what should we test"],
    "MARKDOWN_AUTHORING": ["write the prd", "draft an adr", "write documentation", "draft the readme"],
    "PROJECT_DOCUMENTATION": ["update the docs", "document this"],
    "LOCAL_FILE_DISCOVERY": ["find the file", "where is", "locate the"],
    "LOCAL_REPOSITORY_INVENTORY": ["inventory the repo", "list all", "what files"],
    "LOCAL_SYMBOL_SEARCH": ["find the function", "search for the symbol", "grep for"],
    "TEST_EXECUTION": ["run the tests", "run the suite", "execute tests"],
    "BUILD_EXECUTION": ["build the project", "run the build", "compile"],
    "TASK_EXECUTION": ["run the task", "run the script", "npm run", "make target", "run the job", "task runner", "run the migration", "run the pipeline"],
    "LINT_EXECUTION": ["run lint", "lint the code"],
    "GIT_DIFF_SUMMARY": ["summarize the diff", "diff summary", "diff stat", "what changed", "summarize the changes"],
    "COMMIT_SUMMARY": ["commit message", "write the commit message", "summarize this commit"],
    "MILESTONE_SUMMARY": ["milestone summary", "summarize the milestone", "summarize this release range"],
    "GIT_MILESTONE": ["tag the milestone", "push to staging", "record the milestone"],
    "IMAGE_ASSET_GENERATION": ["generate an image", "create a logo", "ui mockup image", "placeholder image", "generate an icon", "design asset"],
    "GITHUB_VERSION_CONTROL": ["open a pr", "create a pull request", "pull request", "github release", "cut a release", "push a tag", "merge the pr", "pr status"],
    "RUNTIME_VALIDATION": ["start the app", "health check", "smoke test"],
    "FRONTEND_BROWSER_QA": ["browser test", "click through", "test the ui in the browser", "screenshot the"],
    "GIT_CHECKPOINT": ["commit and push", "checkpoint", "make a commit"],
    "GIT_PUSH": ["push to remote", "git push"],
    "CI_MONITORING": ["watch ci", "monitor the pipeline", "ci status"],
    "XCODE_PROJECT_SETUP": ["xcode project", "xcodeproj", "add a target", "scheme setup", "xcconfig", "info.plist", "workspace setup"],
    "APPLE_BUILD_TEST": ["xcodebuild", "swift build", "swift test", "xctest", "build the ios app", "build for tvos", "build for watchos", "run the swift tests"],
    "SIMULATOR_LIFECYCLE": ["simctl", "boot the simulator", "erase the simulator", "pair the watch simulator", "shutdown the simulator"],
    "SIMULATOR_VISUAL_QA": ["simulator screenshot", "check the simulator screen", "dark mode on the simulator", "dynamic type", "safe area"],
    "APPLE_VERIFICATION": ["verify on ios", "run it on the simulator", "test on iphone and ipad", "verify the watch app", "verify on apple tv", "destination matrix"],
    "LONG_RUNNING_JOB": ["long-running", "training run", "large export", "takes hours", "ffmpeg", "batch job"],
    "LOG_TRIAGE": ["triage the logs", "summarize the logs", "compress the log"],
    "MIXED_RESEARCH_AND_IMPLEMENTATION": ["research then implement", "investigate and build"],
    "MIXED_FRONTEND_QA_AND_FIX": ["reproduce and fix the frontend", "qa and fix the ui"],
    "MIXED_CORE_CHANGE_AND_VALIDATION": ["implement and validate", "change and test"],
}


def _merge_hints(policy):
    hints = {k: list(v) for k, v in DEFAULT_INTENT_HINTS.items()}
    extra = (policy or {}).get("intent_hints") or {}
    for task_type, phrases in extra.items():
        if not phrases:
            continue
        hints.setdefault(task_type, [])
        for p in phrases:
            if p not in hints[task_type]:
                hints[task_type].append(p)
    return hints


def infer_task_type(text, hints):
    """Score TASK_TYPEs by phrase hits in `text`. Returns (task_type, strength)
    where strength is 'strong' | 'weak' | 'none'."""
    if not text:
        return None, "none"
    low = text.lower()
    scores = {}
    for task_type, phrases in hints.items():
        score = 0
        for phrase in phrases:
            if phrase in low:
                # longer, more specific phrases weigh more
                score += 1 + phrase.count(" ")
        if score:
            scores[task_type] = score
    if not scores:
        return None, "none"
    best = max(scores, key=lambda k: (scores[k], k))
    top = scores[best]
    # strong if the winner clearly leads or matched a multi-word phrase
    contenders = sorted(scores.values(), reverse=True)
    strong = top >= 2 or len(contenders) == 1
    return best, ("strong" if strong else "weak")


def _stages(decision, primary_agent, persona):
    """Return the ordered stage list for a decision."""
    P = lambda agent, persona_name, action, group=None: {
        "agent": agent, "persona": persona_name, "action": action, "parallel_group": group,
    }
    if decision == "HANDLE_WITH_CLAUDE":
        return [P(CLAUDE, persona or "principal-engineer", "Handle directly: decide and implement.")]
    if decision == "ESCALATE_TO_CLAUDE":
        return [P(CLAUDE, "principal-engineer", "Escalated: Claude takes over the decision.")]
    if decision == "DELEGATE_TO_CODEX":
        return [P(CODEX, persona, "Delegate to Codex; return a structured codex-result.")]
    if decision == "DELEGATE_TO_ANTIGRAVITY":
        return [P(ANTI, persona, "Delegate to Antigravity; return a structured antigravity-result.")]
    if decision == "DELEGATE_TO_OMLX_MONITOR":
        return [P(OMLX, None, "oMLX triages/compresses logs and emits a monitor-report.")]
    if decision == "CODEX_THEN_CLAUDE":
        return [P(CODEX, persona or "codebase-analyst", "Gather local truth: files, git state, analysis."),
                P(CLAUDE, "principal-engineer", "Decide and implement on Codex's evidence.")]
    if decision == "CLAUDE_THEN_CODEX":
        return [P(CLAUDE, persona or "principal-engineer", "Implement the core change."),
                P(CODEX, "qa-runner", "Run change-scoped QA; on pass, commit the change unit per GIT_WORKFLOW.")]
    if decision == "CODEX_THEN_ANTIGRAVITY":
        # Apple verification: Codex drives the Mac; Gemini grades the screens.
        return [P(CODEX, persona or "xcode-controller", "Resolve destinations, build, run unit+UI tests, capture screenshots/recordings/logs."),
                P(ANTI, "simulator-qa-analyst", "Visual QA of captured artifacts: layout, appearance, Dynamic Type, OCR of errors.")]
    if decision == "ANTIGRAVITY_THEN_CODEX":
        # Local Truth Rule: Codex verifies what Gemini reports before Claude acts.
        return [P(ANTI, persona or "web-researcher", "Research live sources / observe visually; return dated, sourced findings."),
                P(CODEX, "research-synthesizer", "Verify findings against local repo state; synthesize the brief.")]
    if decision == "FRONTEND_QA_FIX_LOOP":
        # agy operates the browser and judges visuals, CLAUDE writes the fix,
        # Codex runs the regression and commits the change unit.
        return [P(ANTI, "browser-qa-operator", "Reproduce + capture screenshots/console/network."),
                P(CLAUDE, "principal-engineer", "Fix the frontend (Claude writes the code)."),
                P(CODEX, "qa-runner", "Re-run the failed flow + frontend regression suite."),
                P(ANTI, "frontend-visual-reviewer", "Visual confirmation of the fix from fresh evidence."),
                P(CODEX, "git-steward", "Commit the change unit per GIT_WORKFLOW (agy Flash message).")]
    if decision == "RESEARCH_THEN_IMPLEMENT_THEN_VALIDATE":
        return [P(ANTI, "web-researcher", "Live research: current docs, dated + sourced."),
                P(CODEX, "research-synthesizer", "Verify against the local repo; synthesize an implementation brief."),
                P(CLAUDE, "principal-engineer", "Decide the approach and implement core changes."),
                P(CODEX, "qa-runner", "Validate; on pass record the milestone and push staging per GIT_WORKFLOW.")]
    if decision == "PARALLELIZE_CODEX_AND_ANTIGRAVITY":
        return [P(CODEX, persona or "codebase-analyst", "Local analysis/inventory (parallel).", 0),
                P(ANTI, "web-researcher", "Live research/visual observation (parallel).", 0)]
    if decision in ("CLAUDE_WITH_OMLX_MONITOR", "CODEX_WITH_OMLX_MONITOR", "ANTIGRAVITY_WITH_OMLX_MONITOR"):
        work = {"CLAUDE_WITH_OMLX_MONITOR": CLAUDE, "CODEX_WITH_OMLX_MONITOR": CODEX,
                "ANTIGRAVITY_WITH_OMLX_MONITOR": ANTI}[decision]
        return [P(work, persona, "Run the long job under a supervisor.", 0),
                P(OMLX, None, "Monitor logs, detect stalls, emit completion/escalation events.", 0)]
    # fallback
    return [P(primary_agent, persona, "Handle the task.")]


def route(task_type=None, text=None, long_running=False, large_logs=False,
          task_id=None, policy=None):
    policy = policy if policy is not None else load_policy()
    tun = (policy.get("tunables") or {})
    overrides = (policy.get("overrides") or {})
    matched_by = "explicit_task_type"

    if task_type:
        task_type = task_type.strip().upper()
        if task_type not in ROUTE_TABLE:
            raise ValueError(f"unknown task_type: {task_type}")
        confidence = tun.get("confidence_explicit", 0.95)
    else:
        hints = _merge_hints(policy)
        inferred, strength = infer_task_type(text, hints)
        if inferred:
            task_type = inferred
            matched_by = "intent_inference"
            confidence = tun.get("confidence_inferred_strong", 0.8) if strength == "strong" \
                else tun.get("confidence_inferred_weak", 0.55)
        else:
            task_type = "DO_NOT_DELEGATE"
            matched_by = "default"
            confidence = tun.get("confidence_default", 0.4)

    base_decision, primary, persona, rationale = ROUTE_TABLE[task_type]

    # config override of the decision (validated against the enum)
    if task_type in overrides and overrides[task_type] in _lib.ROUTING_DECISIONS:
        base_decision = overrides[task_type]
        matched_by = "override"
        rationale = f"Override from routing-policy.yaml: {task_type} -> {base_decision}."
        primary = _primary_for(base_decision, primary)

    decision = base_decision
    monitor = base_decision in MONITOR_DECISIONS
    monitor_requested = bool(long_running or large_logs or task_type in ALWAYS_MONITOR)

    if monitor_requested and not monitor:
        if base_decision in MONITOR_UPGRADE:
            decision = MONITOR_UPGRADE[base_decision]
            monitor = True
            rationale += " Long-running/large-log signal: oMLX monitor attached."
        else:
            # pipeline decision: keep order, attach a parallel monitor stage
            monitor = True
            rationale += " Long-running/large-log signal: oMLX monitor runs alongside."

    stages = _stages(decision, primary, persona)
    if monitor and decision not in MONITOR_DECISIONS and not any(s["agent"] == OMLX for s in stages):
        stages.append({"agent": OMLX, "persona": None,
                       "action": "Monitor the long-running stage; emit completion/escalation events.",
                       "parallel_group": 0})

    result = {
        "task_id": task_id or "task-unrouted",
        "task_type": task_type,
        "decision": decision,
        "primary_agent": primary,
        "stages": stages,
        "monitor": monitor,
        "persona": persona,
        "rationale": rationale,
        "confidence": round(float(confidence), 2),
        "alternatives": _alternatives(task_type, decision),
        "escalation": "ESCALATE_TO_CLAUDE",
        "matched_by": matched_by,
        "signals": {"long_running": bool(long_running), "large_logs": bool(large_logs),
                     "text_provided": bool(text)},
    }
    return result


def _primary_for(decision, fallback):
    if decision in ("HANDLE_WITH_CLAUDE", "ESCALATE_TO_CLAUDE", "CLAUDE_WITH_OMLX_MONITOR"):
        return CLAUDE
    if decision in ("DELEGATE_TO_CODEX", "CODEX_WITH_OMLX_MONITOR"):
        return CODEX
    if decision in ("DELEGATE_TO_ANTIGRAVITY", "ANTIGRAVITY_WITH_OMLX_MONITOR"):
        return ANTI
    if decision == "DELEGATE_TO_OMLX_MONITOR":
        return OMLX
    return fallback


def _alternatives(task_type, decision):
    alts = []
    if decision == "HANDLE_WITH_CLAUDE" and task_type == "LOCAL_DEBUGGING":
        alts.append("CODEX_THEN_CLAUDE if local truth (files, git state, failing output) must be gathered first")
    if decision == "DELEGATE_TO_CODEX" and task_type in ("CODEBASE_SEMANTIC_ANALYSIS", "BLAST_RADIUS_ANALYSIS"):
        alts.append("PARALLELIZE_CODEX_AND_ANTIGRAVITY if live research should run alongside local analysis")
    if task_type == "FRONTEND_BUG_FIX":
        alts.append("FRONTEND_QA_FIX_LOOP for the full agy-reproduce -> Claude-fix -> Codex-verify loop")
    if task_type == "APPLE_BUILD_TEST":
        alts.append("APPLE_VERIFICATION for the full build -> test -> simulator visual QA loop")
    return alts


def load_policy():
    try:
        return _lib.load_config("routing-policy.yaml") or {}
    except Exception:
        return {}


# --------------------------------------------------------------------------- #

def _self_check():
    cases = [
        (dict(task_type="LOCAL_CORE_IMPLEMENTATION"), "HANDLE_WITH_CLAUDE", CLAUDE),
        (dict(task_type="LOCAL_BACKEND_IMPLEMENTATION"), "HANDLE_WITH_CLAUDE", CLAUDE),
        (dict(task_type="LOCAL_ARCHITECTURE"), "HANDLE_WITH_CLAUDE", CLAUDE),
        (dict(task_type="FRONTEND_BUG_FIX"), "HANDLE_WITH_CLAUDE", CLAUDE),
        (dict(task_type="LOCAL_FRONTEND_IMPLEMENTATION"), "HANDLE_WITH_CLAUDE", CLAUDE),
        # Codex: local truth + repo intelligence
        (dict(task_type="CODEBASE_SEMANTIC_ANALYSIS"), "DELEGATE_TO_CODEX", CODEX),
        (dict(task_type="PARALLEL_INVESTIGATION"), "DELEGATE_TO_CODEX", CODEX),
        (dict(task_type="LOCAL_FILE_DISCOVERY"), "DELEGATE_TO_CODEX", CODEX),
        (dict(task_type="TEST_EXECUTION"), "DELEGATE_TO_CODEX", CODEX),
        (dict(task_type="GIT_PUSH"), "DELEGATE_TO_CODEX", CODEX),
        (dict(task_type="GIT_MILESTONE"), "DELEGATE_TO_CODEX", CODEX),
        (dict(task_type="GITHUB_VERSION_CONTROL"), "DELEGATE_TO_CODEX", CODEX),
        (dict(task_type="TASK_EXECUTION"), "DELEGATE_TO_CODEX", CODEX),
        (dict(task_type="XCODE_PROJECT_SETUP"), "DELEGATE_TO_CODEX", CODEX),
        (dict(task_type="SIMULATOR_LIFECYCLE"), "DELEGATE_TO_CODEX", CODEX),
        (dict(task_type="APPLE_BUILD_TEST"), "CODEX_WITH_OMLX_MONITOR", CODEX),
        (dict(task_type="APPLE_VERIFICATION"), "CODEX_THEN_ANTIGRAVITY", CODEX),
        # Antigravity (Gemini): web + visual + narrative
        (dict(task_type="CURRENT_INFORMATION"), "DELEGATE_TO_ANTIGRAVITY", ANTI),
        (dict(task_type="WEB_RESEARCH"), "DELEGATE_TO_ANTIGRAVITY", ANTI),
        (dict(task_type="FRONTEND_VISUAL_REVIEW"), "DELEGATE_TO_ANTIGRAVITY", ANTI),
        (dict(task_type="FRONTEND_BROWSER_QA"), "DELEGATE_TO_ANTIGRAVITY", ANTI),
        (dict(task_type="SIMULATOR_VISUAL_QA"), "DELEGATE_TO_ANTIGRAVITY", ANTI),
        (dict(task_type="GIT_DIFF_SUMMARY"), "DELEGATE_TO_ANTIGRAVITY", ANTI),
        (dict(task_type="COMMIT_SUMMARY"), "DELEGATE_TO_ANTIGRAVITY", ANTI),
        (dict(task_type="MILESTONE_SUMMARY"), "DELEGATE_TO_ANTIGRAVITY", ANTI),
        # long-running + pipelines
        (dict(task_type="LONG_RUNNING_JOB"), "CODEX_WITH_OMLX_MONITOR", CODEX),
        (dict(task_type="TEST_EXECUTION", long_running=True), "CODEX_WITH_OMLX_MONITOR", CODEX),
        (dict(task_type="MIXED_FRONTEND_QA_AND_FIX"), "FRONTEND_QA_FIX_LOOP", CLAUDE),
        (dict(task_type="MIXED_RESEARCH_AND_IMPLEMENTATION"), "RESEARCH_THEN_IMPLEMENT_THEN_VALIDATE", CLAUDE),
        (dict(task_type="MIXED_CORE_CHANGE_AND_VALIDATION"), "CLAUDE_THEN_CODEX", CLAUDE),
    ]
    for kwargs, decision, agent in cases:
        r = route(**kwargs, policy={})
        assert r["decision"] == decision, (kwargs, r["decision"], decision)
        assert r["primary_agent"] == agent, (kwargs, r["primary_agent"], agent)
        errs = _lib.validate_against_file(r, "routing-decision.schema.json")
        assert not errs, (kwargs, errs)
    # long-running attaches a monitor
    assert route(task_type="TEST_EXECUTION", long_running=True, policy={})["monitor"] is True
    assert any(s["agent"] == OMLX for s in route(task_type="BUILD_EXECUTION", large_logs=True, policy={})["stages"])
    # Apple verification always carries a monitor (long-running by definition)
    r = route(task_type="APPLE_VERIFICATION", policy={})
    assert r["monitor"] is True and any(s["agent"] == OMLX for s in r["stages"])
    # Claude never loses implementation; Codex never gains it
    for tt in ("LOCAL_FRONTEND_IMPLEMENTATION", "FRONTEND_BUG_FIX", "LOCAL_CORE_IMPLEMENTATION"):
        assert route(task_type=tt, policy={})["primary_agent"] == CLAUDE, tt
    # inference
    r = route(text="trace how the request flows through the backend service", policy={})
    assert r["matched_by"] == "intent_inference", r["matched_by"]
    # determinism: identical inputs -> identical decision
    a = route(task_type="WEB_RESEARCH", policy={})
    b = route(task_type="WEB_RESEARCH", policy={})
    assert a["decision"] == b["decision"] == "DELEGATE_TO_ANTIGRAVITY"
    # every task type routes and validates
    for tt in _lib.TASK_TYPES:
        r = route(task_type=tt, policy={})
        assert not _lib.validate_against_file(r, "routing-decision.schema.json"), (tt,)
    print("OK route-task self-check passed ({} task types)".format(len(_lib.TASK_TYPES)))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Route a unit of work to the right agent(s).")
    ap.add_argument("--task-type", help="explicit TASK_TYPE (see _lib.TASK_TYPES)")
    ap.add_argument("--text", help="free-text task description (inference fallback)")
    ap.add_argument("--task-id", default=None)
    ap.add_argument("--long-running", action="store_true")
    ap.add_argument("--large-logs", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args(argv)

    if args.self_check:
        _self_check()
        return 0

    text = args.text
    if not args.task_type and not text and not sys.stdin.isatty():
        text = sys.stdin.read().strip() or None

    try:
        decision = route(task_type=args.task_type, text=text,
                         long_running=args.long_running, large_logs=args.large_logs,
                         task_id=args.task_id)
    except ValueError as e:
        print(json.dumps({"error": str(e), "valid_task_types": _lib.TASK_TYPES}), file=sys.stderr)
        return 2
    print(json.dumps(decision, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
