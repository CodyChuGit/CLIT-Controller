"""Task A7 — engine-derived task pipeline.

The engine decides *who* runs each step (fallback-aware, honoring user routing)
and, when confident, *which* steps run in *what* order. Engine stage personas are
mapped onto AgentComposer's existing step ids so the executor, queue, and
frontend chips are reused unchanged.
"""

from __future__ import annotations

from typing import Optional

from . import _engine, caps, dispatch_adapter, router

# engine persona -> existing AgentComposer step id
PERSONA_STEP: dict[str, str] = {
    # planning / analysis / research -> spec step
    "spec-writer": "codex_spec",
    "research-synthesizer": "codex_spec",
    "codebase-analyst": "codex_spec",
    "parallel-investigation-lead": "codex_spec",
    "test-strategy-designer": "codex_spec",
    "technical-writer": "codex_spec",
    "repository-navigator": "codex_spec",
    "web-researcher": "codex_spec",
    "api-documentation-specialist": "codex_spec",
    "github-scout": "codex_spec",
    "github-code-investigator": "codex_spec",
    "dependency-auditor": "codex_spec",
    # implementation -> implement step (Claude)
    "implementer": "claude_implement",
    # qa / test / runtime / visual -> qa step
    "qa-runner": "gemini_qa",
    "qa-reporter": "gemini_qa",
    "browser-qa-operator": "gemini_qa",
    "frontend-visual-reviewer": "gemini_qa",
    "simulator-qa-analyst": "gemini_qa",
    "runtime-validator": "gemini_qa",
    "environment-operator": "gemini_qa",
    "task-runner": "gemini_qa",
    # review -> review step
    "independent-reviewer": "codex_review",
}


def effective_provider(preferred: str, usage_state: Optional[dict] = None) -> str:
    """The user's preferred provider, unless it is exhausted (per engine usage
    state) — then the engine's spread-first fallback. Honors user routing while
    adding exhaustion-aware fallback. Claude/unknown providers pass through
    (Claude is always available)."""
    if preferred not in ("codex", "antigravity"):
        return preferred
    ns = _engine.load()
    state = usage_state if usage_state is not None else ns.usage_lib.load_state()
    effective, _hops = ns.usage_lib.resolve(preferred, caps.installed_agents(), state)
    return effective


def engine_pipeline(goal: str, task_type: Optional[str] = None) -> Optional[list[tuple[str, Optional[str], str]]]:
    """If the engine yields a confident multi-stage pipeline for this task, return
    it as ``[(step_id, provider)]``; else ``None`` (caller keeps the default
    sequence). Monitor (oMLX) stages are dropped; consecutive duplicate steps are
    collapsed. Only overrides the default when confident (>=0.8) and >1 mapped step,
    so free-form goals keep the familiar spec->implement->qa->review flow."""
    rr = router.route_for_task(goal, task_type=task_type)
    seq: list[tuple[str, Optional[str], str]] = []
    for p in dispatch_adapter.plan(rr):
        if p.monitor or p.provider_id is None:
            continue
        step = PERSONA_STEP.get(p.persona)
        if step is None:
            continue
        if seq and seq[-1][0] == step:
            continue
        seq.append((step, p.provider_id, p.persona))
    if len(seq) > 1 and rr.confidence >= 0.8:
        return seq
    return None
