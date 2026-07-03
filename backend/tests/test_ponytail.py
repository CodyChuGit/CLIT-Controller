"""Ponytail — the output-side half of the token strategy (Headroom is input-side).

Every agent step prompt must carry the minimalism ladder so agents write less
code and shorter docs; the level is configurable and 'off' removes it cleanly.
"""

from __future__ import annotations

import copy

from agentflow import config, ponytail, prompt_templates
from agentflow.usage_service import DEFAULT_USAGE


def usage() -> dict:
    return copy.deepcopy(DEFAULT_USAGE)


def test_levels_and_blocks():
    assert ponytail.block("off") == ""
    assert "YAGNI" in ponytail.block("lite")
    assert "YAGNI" in ponytail.block("full")
    assert len(ponytail.block("lite")) < len(ponytail.block("full")) < len(ponytail.block("ultra"))
    # never simplify away the guardrails
    assert "security" in ponytail.block("full")


def test_default_level_is_full_and_invalid_falls_back():
    assert ponytail.level() == "full"  # hermetic home → no config → default
    config.update_settings(ponytail={"level": "bogus"})
    assert ponytail.level() == "full"


def test_settings_roundtrip():
    config.update_settings(ponytail={"level": "ultra"})
    assert ponytail.level() == "ultra"
    config.update_settings(ponytail={"level": "off"})
    assert ponytail.level() == "off"


def test_step_prompts_carry_the_ladder():
    prompt = prompt_templates.claude_implement_prompt(usage(), ".agentflow/tasks/t1")
    assert "Ponytail" in prompt and "YAGNI" in prompt
    # the ladder rides AFTER the step body, never replacing it
    assert "Implement only the requested production changes." in prompt


def test_controller_chat_prompt_carries_the_ladder():
    prompt = prompt_templates.orchestrator_chat_prompt(usage(), "ws", "", "build a thing")
    assert "YAGNI" in prompt


def test_off_removes_ponytail_everywhere():
    config.update_settings(ponytail={"level": "off"})
    step = prompt_templates.claude_implement_prompt(usage(), ".agentflow/tasks/t1")
    chat = prompt_templates.orchestrator_chat_prompt(usage(), "ws", "", "hi")
    assert "Ponytail" not in step and "YAGNI" not in step
    assert "YAGNI" not in chat


def test_direct_chat_prompt_stays_unshaped():
    # Direct chat is the user's own conversation — no injected discipline.
    prompt = prompt_templates.direct_chat_prompt("claude", "", "hello")
    assert "YAGNI" not in prompt
