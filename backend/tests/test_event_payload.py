"""Typed OutputEvent payload pipeline (I/O rebuild, Plane 2).

The event bus now attaches a typed, discriminated `payload` to each semantic event
(alongside the legacy fields). These payloads must validate against the
io_contracts envelope, carry no secrets, and be absent for transport-only events."""

from __future__ import annotations

from agentflow import event_bus, io_contracts


def _envelope(ev: dict) -> dict:
    return {
        "schemaVersion": "1",
        "id": str(ev["id"]),
        "workspaceId": ev.get("workspacePath") or "/ws",
        "createdAt": ev["createdAt"],
        "redacted": ev["redacted"],
        "truncated": ev["truncated"],
        "payload": ev["payload"],
    }


def test_bus_events_carry_valid_typed_payloads():
    bus = event_bus.EventBus()
    cases = [
        bus.publish("/ws", "controller.delta", text_delta="hello"),
        bus.publish("/ws", "run.output", channel="stdout", text_delta="line"),
        bus.publish("/ws", "command.started", data={"command": "npm test"}),
        bus.publish("/ws", "command.finished", data={"status": "succeeded", "exitCode": 0, "durationMs": 12}),
        bus.publish("/ws", "run.cancelled", data={"runId": "r1"}),
        bus.publish("/ws", "approval.required", data={"approvalId": "a1", "action": "git push", "reason": "remote"}),
        bus.publish("/ws", "policy.denied", data={"reason": "shell operators"}),
        bus.publish("/ws", "task.summary_ready", data={"kind": "task_summary"}),
    ]
    for ev in cases:
        assert ev["payload"] is not None, ev["type"]
        env, err = io_contracts.validate_event(_envelope(ev))
        assert err is None, (ev["type"], err)
    expected = {
        "narrative.delta",
        "command.output",
        "command.started",
        "command.completed",
        "cancellation",
        "approval.requested",
        "failure",
        "summary.ready",
    }
    assert {ev["payload"]["type"] for ev in cases} == expected


def test_transport_only_events_have_no_typed_payload():
    bus = event_bus.EventBus()
    assert bus.publish("/ws", "run.heartbeat", data={"elapsedMs": 10})["payload"] is None
    assert bus.publish("/ws", "queue.enqueued", data={"itemId": "x"})["payload"] is None


def test_payload_is_redacted():
    bus = event_bus.EventBus()
    secret = "ghp_" + "A" * 36
    ev = bus.publish("/ws", "controller.delta", text_delta=f"token {secret}")
    assert secret not in str(ev["payload"]) and "[REDACTED]" in str(ev["payload"])
