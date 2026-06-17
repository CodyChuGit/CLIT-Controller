"""Regression tests for live text streaming (event bus + subprocess deltas)."""

import asyncio
import sys

from agentflow import event_bus
from agentflow.process_runner import RUNNER, _split_emittable


def test_split_emittable_cuts_at_whitespace_and_holds_tail():
    emit, rest = _split_emittable("hello world frag")
    assert emit == "hello world " and rest == "frag"
    # No whitespace and under the cap -> hold everything (don't split a token).
    assert _split_emittable("nospace") == ("", "nospace")


def test_event_bus_redacts_filters_and_resumes():
    ws = "/tmp/ws-stream-A"
    e = event_bus.BUS.publish(ws, "run.output", channel="stdout", text_delta="API_KEY=topsecret\n", run_id="r1")
    assert "topsecret" not in (e["textDelta"] or "") and "[REDACTED]" in e["textDelta"]
    # Visible from before its id, excluded once resumed past it (dedupe-by-id).
    assert any(x["id"] == e["id"] for x in event_bus.BUS.events_after(ws, after_id=e["id"] - 1))
    assert all(x["id"] != e["id"] for x in event_bus.BUS.events_after(ws, after_id=e["id"]))
    # Workspace-scoped: a different workspace never sees it.
    assert all(x["id"] != e["id"] for x in event_bus.BUS.events_after("/tmp/ws-stream-B", after_id=0))


def _run(cmd, ws, stream_kind):
    async def go():
        before = event_bus.BUS.cursor()
        record, consume = await RUNNER.start(
            cmd, ws, provider="test", workspace=ws, stream_kind=stream_kind
        )
        await consume
        return record, event_bus.BUS.events_after(ws, after_id=before)

    return asyncio.run(go())


def test_subprocess_streams_redacted_ordered_deltas(tmp_path):
    cmd = [sys.executable, "-c", "print('hello world'); print('API_KEY=topsecret')"]
    record, events = _run(cmd, tmp_path, "run")
    assert record.status == "succeeded"
    text = "".join(e["textDelta"] or "" for e in events if e["type"] == "run.output")
    assert "hello world" in text
    assert "topsecret" not in text and "[REDACTED]" in text  # redacted before broadcast
    seqs = [e["sequence"] for e in events if e["runId"] == record.id and e["sequence"] is not None]
    assert seqs == sorted(seqs) and len(seqs) >= 1  # per-run ordering preserved


def test_command_run_emits_lifecycle(tmp_path):
    cmd = [sys.executable, "-c", "print('done')"]
    _record, events = _run(cmd, tmp_path, "command")
    types = [e["type"] for e in events]
    assert "command.started" in types and "command.finished" in types
    assert any(e["type"] == "run.output" and "done" in (e["textDelta"] or "") for e in events)
