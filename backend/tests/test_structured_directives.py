"""Pillar 5 — native structured controller output.

The controller may emit a fenced ``agentflow`` JSON block of validated decisions;
the parsers are structured-first with markdown fallback, so every consumer gains
structured support with no change and legacy markdown still works.
"""

from __future__ import annotations

from agentflow import chat_directives as cd


def _block(json_str: str) -> str:
    return f"intro text\n```agentflow\n{json_str}\n```\ntrailing"


def test_structured_task_envelope_parses():
    text = _block(
        '{"version":"1","decisions":[{"kind":"task","title":"Add login","goal":"impl login","queueSteps":["codex_spec"]}]}'
    )
    assert cd.parse_task_directive(text) == ("Add login", "impl login", ["codex_spec"])


def test_structured_queue_and_run_and_done():
    text = _block(
        '{"version":"1","decisions":['
        '{"kind":"queue","taskRef":"latest","steps":["claude_implement","gemini_qa"]},'
        '{"kind":"run","command":"npm test"},'
        '{"kind":"run","command":"git status"},'
        '{"kind":"done","reason":"shipped"}]}'
    )
    assert cd.parse_queue_directive(text) == ("latest", ["claude_implement", "gemini_qa"])
    assert cd.parse_run_directives(text) == ["npm test", "git status"]
    assert cd.parse_done_directive(text) == "shipped"
    assert cd.parse_needs_user_directive(text) is None


def test_structured_queuesteps_full_expands():
    text = _block('{"decisions":[{"kind":"task","title":"X","goal":"Y","queueSteps":["full"]}]}')
    _t, _g, steps = cd.parse_task_directive(text)
    assert steps == list(cd.FULL_SEQUENCE)


def test_structured_run_capped_at_three():
    text = _block(
        '{"decisions":['
        '{"kind":"run","command":"a"},{"kind":"run","command":"b"},'
        '{"kind":"run","command":"c"},{"kind":"run","command":"d"}]}'
    )
    assert cd.parse_run_directives(text) == ["a", "b", "c"]


def test_bare_object_and_list_forms_accepted():
    assert cd.parse_done_directive(_block('{"kind":"done","reason":"ok"}')) == "ok"
    assert cd.parse_run_directives(_block('[{"kind":"run","command":"ls"}]')) == ["ls"]


def test_structured_first_ignores_markdown_when_both_present():
    # A valid structured block wins; the legacy markdown task block is NOT also parsed.
    text = (
        "```agentflow\n"
        '{"decisions":[{"kind":"run","command":"npm test"}]}'
        "\n```\n"
        "```agentflow-task\ntitle: ghost\ngoal: should be ignored\n```\n"
    )
    assert cd.parse_run_directives(text) == ["npm test"]
    assert cd.parse_task_directive(text) is None  # structured present, no task in it


def test_invalid_structured_decisions_dropped_safely():
    # missing required fields / unknown kind → skipped; valid sibling still parses.
    text = _block('{"decisions":[{"kind":"task","title":"only-title"},{"kind":"bogus"},{"kind":"run","command":"ok"}]}')
    assert cd.parse_run_directives(text) == ["ok"]
    assert cd.parse_task_directive(text) is None  # task missing goal -> invalid, dropped


def test_malformed_json_falls_back_to_markdown():
    text = "```agentflow\n{not valid json}\n```\n```agentflow-run\ncommand: npm test\n```"
    # the agentflow block is malformed (no valid decisions) → markdown path used
    assert cd.parse_run_directives(text) == ["npm test"]


def test_strip_action_blocks_removes_structured_block():
    text = 'Hello\n```agentflow\n{"decisions":[{"kind":"run","command":"x"}]}\n```\nBye'
    out = cd.strip_action_blocks(text)
    assert "agentflow" not in out and "Hello" in out and "Bye" in out


def test_legacy_markdown_still_works():
    text = "```agentflow-task\ntitle: Legacy\ngoal: still parses\nqueue: full\n```"
    assert cd.parse_task_directive(text) == ("Legacy", "still parses", list(cd.FULL_SEQUENCE))


def test_records_bridge_reflects_structured():
    text = _block('{"decisions":[{"kind":"task","title":"T","goal":"G"},{"kind":"run","command":"go"}]}')
    kinds = [r["kind"] for r in cd.controller_directive_records(text)]
    assert "task" in kinds and "run" in kinds
