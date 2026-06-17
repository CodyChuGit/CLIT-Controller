"""CLITC_RESULT_V1 is the PRIMARY controller protocol in the parse_* path.

Proves the rebuild's keystone wiring: chat_directives reads the deterministic
protocol first; a valid v1 block drives the action; an invalid or non-matching v1
block yields no directive (so chat_service mutates no state) and is NEVER silently
downgraded to the legacy parsers; the v1 block never renders as prose; and when no
v1 block is present the legacy forms still work (migration fallback).
"""

from __future__ import annotations

from agentflow import chat_directives as cd
from agentflow.controller_protocol import CLOSE, OPEN


def _v1(action_json: str, message: str = '{"summary":"ok"}') -> str:
    body = f'{{"schemaVersion":"1","kind":"controller_result","message":{message},"action":{action_json}}}'
    return f"reasoning prose\n\n{OPEN}\n{body}\n{CLOSE}\n"


def test_v1_create_task_drives_parse_task():
    text = _v1('{"type":"create_task","title":"Add login","goal":"impl login","steps":["codex_spec"]}')
    assert cd.parse_task_directive(text) == ("Add login", "impl login", ["codex_spec"])


def test_v1_queue_steps_drives_parse_queue():
    text = _v1('{"type":"queue_steps","taskId":"t1","steps":["claude_implement","gemini_qa"]}')
    assert cd.parse_queue_directive(text) == ("t1", ["claude_implement", "gemini_qa"])


def test_v1_run_command_drives_parse_run():
    text = _v1('{"type":"run_command","command":"npm test"}')
    assert cd.parse_run_directives(text) == ["npm test"]


def test_v1_complete_and_request_user_reasons():
    assert cd.parse_done_directive(_v1('{"type":"complete_task","reason":"shipped"}')) == "shipped"
    assert cd.parse_needs_user_directive(_v1('{"type":"request_user","reason":"need decision"}')) == "need decision"


def test_v1_answer_action_yields_no_directives():
    text = _v1('{"type":"answer"}')
    assert cd.parse_task_directive(text) is None
    assert cd.parse_queue_directive(text) is None
    assert cd.parse_run_directives(text) == []
    assert cd.parse_done_directive(text) is None


def test_invalid_v1_never_falls_back_to_legacy_and_surfaces_failure():
    # An invalid v1 block is present AND a legacy markdown block is present. The
    # legacy block must NOT be honored (no silent downgrade), and no directive runs.
    text = (
        f"{OPEN}\n"
        '{"schemaVersion":"1","kind":"controller_result","action":{"type":"frobnicate"}}'
        f"\n{CLOSE}\n"
        "```agentflow-run\ncommand: rm -rf /\n```\n"
    )
    assert cd.parse_run_directives(text) == []  # legacy run NOT executed
    assert cd.parse_task_directive(text) is None
    failure = cd.controller_failure(text)
    assert failure is not None  # a typed failure is available to surface


def test_v1_block_is_stripped_from_prose():
    text = _v1('{"type":"answer"}', message='{"summary":"hello"}')
    out = cd.strip_action_blocks(text)
    assert OPEN not in out and CLOSE not in out and "schemaVersion" not in out
    assert "reasoning prose" in out


def test_no_v1_block_legacy_still_works():
    # Migration fallback: no sentinel block → legacy markdown still parses.
    text = "```agentflow-task\ntitle: Legacy\ngoal: still works\nqueue: full\n```"
    assert cd.parse_task_directive(text) == ("Legacy", "still works", list(cd.FULL_SEQUENCE))
    assert cd.parse_run_directives("```agentflow-run\ncommand: npm test\n```") == ["npm test"]
