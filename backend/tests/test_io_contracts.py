"""Typed input/output contract tests (I/O rebuild, Phase 1)."""

from __future__ import annotations

from agentflow import io_contracts as io


def test_input_submission_with_task_destination_and_references():
    sub, err = io.validate_submission(
        {
            "schemaVersion": "1",
            "id": "s1",
            "workspaceId": "/ws",
            "destination": {"kind": "task", "taskId": "t1", "intent": "retry"},
            "content": {
                "text": "redo it",
                "references": [{"kind": "file", "path": "a.py"}, {"kind": "run", "runId": "r1"}],
            },
            "behavior": {"submitMode": "retry"},
            "createdAt": "2026-06-18T00:00:00Z",
        }
    )
    assert err is None
    assert sub.destination.kind == "task" and sub.destination.intent == "retry"
    assert [r.kind for r in sub.content.references] == ["file", "run"]
    assert sub.behavior.submitMode == "retry"


def test_input_submission_destinations_are_typed():
    base = {"schemaVersion": "1", "id": "s", "workspaceId": "/ws", "content": {"text": "hi"}, "createdAt": "t"}
    assert io.validate_submission({**base, "destination": {"kind": "controller"}})[0].destination.kind == "controller"
    prov = io.validate_submission({**base, "destination": {"kind": "provider", "provider": "claude"}})[0]
    assert prov.destination.provider == "claude"


def test_input_submission_rejects_empty_text_and_unknown_destination():
    assert (
        io.validate_submission(
            {
                "schemaVersion": "1",
                "id": "s",
                "workspaceId": "/ws",
                "destination": {"kind": "controller"},
                "content": {"text": ""},
                "createdAt": "t",
            }
        )[1]
        is not None
    )
    assert (
        io.validate_submission(
            {
                "schemaVersion": "1",
                "id": "s",
                "workspaceId": "/ws",
                "destination": {"kind": "bogus"},
                "content": {"text": "x"},
                "createdAt": "t",
            }
        )[1]
        is not None
    )


def test_output_event_payload_union_validates():
    base = {"schemaVersion": "1", "id": "e", "workspaceId": "/ws", "createdAt": "t"}
    env, err = io.validate_event({**base, "payload": {"type": "command.started", "command": "npm test"}})
    assert err is None and env.payload.type == "command.started" and env.payload.command == "npm test"
    env2, _ = io.validate_event({**base, "channel": "stdout", "payload": {"type": "command.output", "text": "line"}})
    assert env2.channel == "stdout" and env2.payload.text == "line"


def test_output_event_rejects_unknown_payload_type():
    env, err = io.validate_event(
        {"schemaVersion": "1", "id": "e", "workspaceId": "/ws", "createdAt": "t", "payload": {"type": "nope"}}
    )
    assert env is None and err is not None
