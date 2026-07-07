"""Task A8 — engine stages build persona-scoped prompts; legacy steps keep templates."""

from __future__ import annotations

import copy

from agentflow import task_service
from agentflow.usage_service import DEFAULT_USAGE


def _usage():
    return copy.deepcopy(DEFAULT_USAGE)


def test_persona_prompt_used_when_persona_given():
    p = task_service._build_step_prompt(_usage(), "t1", "gemini_qa", "qa-runner")
    assert "qa-runner" in p
    assert ".agentflow/tasks/t1" in p


def test_step_template_used_when_no_persona():
    p = task_service._build_step_prompt(_usage(), "t1", "codex_spec", None)
    assert "01_CODEX_SPEC.md" in p  # the hand-tuned legacy template
