"""Regression tests for structured-payload redaction (audit P1-02).

A credential embedded in a command/action must not leak into the durable event
ledger, the live SSE buffer, or the approvals display — only the on-disk approval
record keeps the raw action (so an approved command can be replayed verbatim).
"""

from __future__ import annotations

from agentflow import event_bus, state_store
from agentflow.redaction import redact_data

SECRET = "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
CMD = f"git remote add origin https://cody:{SECRET}@github.com/cody/x.git"


def test_redact_data_walks_nested_structures():
    out = redact_data({"command": CMD, "nested": ["x", {"token": SECRET}]})
    assert SECRET not in str(out)


def test_event_bus_payload_is_redacted():
    bus = event_bus.EventBus()
    event = bus.publish("/ws", "policy.denied", detail=f"denied: {CMD}", data={"command": CMD})
    assert SECRET not in event["detail"]
    assert SECRET not in str(event["data"])


def test_durable_event_and_sse_redacted_but_approval_replayable(tmp_path):
    # create_approval persists the raw action AND mirrors an event carrying it.
    state_store.create_approval(tmp_path, action=CMD, reason=f"remote add {CMD}")

    # Durable timeline (events.json) must not contain the secret.
    events = state_store.read_events(tmp_path)
    assert events, "expected an approval.required event"
    assert SECRET not in str(events)

    # Live SSE buffer must not contain the secret.
    live = event_bus.BUS.events_after(tmp_path, 0)
    assert SECRET not in str(live)

    # Approvals *display* is redacted...
    shown = state_store.list_approvals(tmp_path)
    assert shown and SECRET not in str(shown)

    # ...but the on-disk record keeps the raw action so approve can replay it.
    approval_id = shown[0]["id"]
    raw = state_store.get_approval(tmp_path, approval_id)
    assert raw is not None and SECRET in raw["action"]
