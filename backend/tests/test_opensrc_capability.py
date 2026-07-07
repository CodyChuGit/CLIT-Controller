"""C3 — every task agent is told it can fetch open-source with `opensrc path`."""

from __future__ import annotations

import copy

from agentflow import prompt_templates, task_service
from agentflow.usage_service import DEFAULT_USAGE


def _usage():
    return copy.deepcopy(DEFAULT_USAGE)


def test_legacy_step_prompt_advertises_opensrc():
    assert "opensrc path" in prompt_templates.codex_spec_prompt(_usage(), "tasks/t1")


def test_engine_stage_prompt_advertises_opensrc():
    p = task_service._build_step_prompt(_usage(), "t1", "gemini_qa", "qa-runner")
    assert "opensrc path" in p
