"""Task A7 — engine-derived pipeline: provider fallback + persona->step mapping."""

from __future__ import annotations

from agentflow.orchestrator import pipeline

_EXHAUSTED = {
    "agents": {"codex": {"status": "exhausted", "cooldown_until": 9_999_999_999}},
    "events": {},
}


def test_effective_provider_passes_through_claude_and_unknown():
    assert pipeline.effective_provider("claude") == "claude"
    assert pipeline.effective_provider("git") == "git"


def test_effective_provider_falls_back_when_preferred_exhausted():
    # Codex exhausted -> anything but codex (antigravity if installed, else claude).
    assert pipeline.effective_provider("codex", usage_state=_EXHAUSTED) != "codex"


def test_effective_provider_keeps_preferred_when_clean():
    # With a clean state, an installed preferred provider is kept as-is.
    from agentflow.orchestrator import caps

    if caps.installed_agents()["codex"]:
        assert pipeline.effective_provider("codex", usage_state={"agents": {}, "events": {}}) == "codex"


def test_generic_goal_keeps_default_sequence():
    assert pipeline.engine_pipeline("do the thing") is None


def test_persona_step_map_covers_the_four_lanes():
    assert pipeline.PERSONA_STEP["spec-writer"] == "codex_spec"
    assert pipeline.PERSONA_STEP["implementer"] == "claude_implement"
    assert pipeline.PERSONA_STEP["qa-runner"] == "gemini_qa"
    assert pipeline.PERSONA_STEP["independent-reviewer"] == "codex_review"
