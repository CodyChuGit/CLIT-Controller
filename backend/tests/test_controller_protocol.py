"""Deterministic controller protocol tests (I/O rebuild, Phase 2).

Covers the mission's required backend-contract cases: every action type, unknown
action, missing field, malformed JSON, oversized result, multiple blocks, block
mixed with prose, no block, unsupported version — and that invalid output yields a
failure with NO result (so callers mutate no state).
"""

from __future__ import annotations

from agentflow import controller_protocol as cp


def _frame(body: str) -> str:
    return f"some narrative reasoning\n\n{cp.OPEN}\n{body}\n{cp.CLOSE}\n\ntrailing prose"


def test_each_action_type_validates():
    cases = {
        "answer": '{"type":"answer"}',
        "create_task": '{"type":"create_task","title":"T","goal":"G","steps":["codex_spec"]}',
        "queue_steps": '{"type":"queue_steps","taskId":"t1","steps":["claude_implement"]}',
        "run_command": '{"type":"run_command","command":"npm test"}',
        "request_approval": '{"type":"request_approval","command":"git push","reason":"remote"}',
        "request_user": '{"type":"request_user","reason":"need a decision"}',
        "retry": '{"type":"retry","taskId":"t1","step":"claude_implement"}',
        "reroute": '{"type":"reroute","taskId":"t1","step":"qa","provider":"antigravity"}',
        "complete_task": '{"type":"complete_task","taskId":"t1","reason":"done"}',
        "cancel": '{"type":"cancel"}',
    }
    for atype, action in cases.items():
        body = f'{{"schemaVersion":"1","kind":"controller_result","action":{action}}}'
        result, failure, meta = cp.parse_controller_result(_frame(body))
        assert failure is None, f"{atype}: {failure}"
        assert result is not None and result.action.type == atype
        assert meta.source == "v1" and meta.blocks == 1


def test_prose_tolerant_extraction():
    body = '{"schemaVersion":"1","kind":"controller_result","message":{"summary":"hi"},"action":{"type":"answer"}}'
    result, failure, _ = cp.parse_controller_result("lots of\nprose before " + _frame(body) + " and after")
    assert failure is None and result.message.summary == "hi"


def test_no_block_returns_source_none_for_legacy_fallback():
    result, failure, meta = cp.parse_controller_result("just prose, no result block")
    assert result is None and failure is None and meta.source == "none"


def test_malformed_json_fails_with_no_result():
    result, failure, _ = cp.parse_controller_result(_frame("{not valid json"))
    assert result is None and failure is not None and "Malformed" in failure.title


def test_unknown_action_fails():
    body = '{"schemaVersion":"1","kind":"controller_result","action":{"type":"frobnicate"}}'
    result, failure, _ = cp.parse_controller_result(_frame(body))
    assert result is None and failure is not None


def test_missing_required_field_fails():
    body = '{"schemaVersion":"1","kind":"controller_result","action":{"type":"queue_steps","taskId":"t1"}}'  # steps missing
    result, failure, _ = cp.parse_controller_result(_frame(body))
    assert result is None and failure is not None


def test_unsupported_version_fails():
    body = '{"schemaVersion":"2","kind":"controller_result","action":{"type":"answer"}}'
    result, failure, _ = cp.parse_controller_result(_frame(body))
    assert result is None and failure is not None and "version" in failure.title.lower()


def test_oversized_result_rejected():
    big = (
        '{"schemaVersion":"1","kind":"controller_result","action":{"type":"request_user","reason":"'
        + "x" * 20000
        + '"}}'
    )
    result, failure, _ = cp.parse_controller_result(_frame(big))
    assert result is None and failure is not None and "large" in failure.title.lower()


def test_multiple_blocks_last_wins_and_count_reported():
    b1 = f'{cp.OPEN}\n{{"schemaVersion":"1","kind":"controller_result","action":{{"type":"answer"}}}}\n{cp.CLOSE}'
    b2 = f'{cp.OPEN}\n{{"schemaVersion":"1","kind":"controller_result","action":{{"type":"run_command","command":"ls"}}}}\n{cp.CLOSE}'
    result, failure, meta = cp.parse_controller_result(f"prose\n{b1}\nmore\n{b2}")
    assert failure is None and result.action.type == "run_command"
    assert meta.blocks == 2  # misbehaviour signal surfaced


def test_action_types_cover_the_closed_set():
    assert set(cp.ACTION_TYPES) == {
        "answer",
        "create_task",
        "queue_steps",
        "run_command",
        "request_approval",
        "request_user",
        "retry",
        "reroute",
        "complete_task",
        "cancel",
    }
