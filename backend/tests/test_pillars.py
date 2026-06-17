"""Cross-cutting pillar acceptance tests (docs/PILLARS.md).

These encode the product pillars as success metrics rather than testing
implementation trivia. Pillar 1 and Pillar 5 have dedicated suites
(test_headroom_service.py, test_contracts.py); this module proves the backend
half of Pillar 2 (true live output) and Pillar 3 (secrets never reach the stream).
"""

from __future__ import annotations

import asyncio
import sys

from agentflow import event_bus
from agentflow.process_runner import ProcessRunner


def test_pillar2_output_is_visible_before_process_exits(tmp_path):
    """Pillar 2: the first usable chunk must stream before its producer completes.

    Deterministic proof: a child prints a chunk, then stays alive ~1s. We assert a
    delta carrying that chunk is on the event bus *while the run is still running*
    (status == 'running'), not only after exit.
    """

    async def go():
        runner = ProcessRunner()
        argv = [sys.executable, "-u", "-c", "import time; print('CHUNK', flush=True); time.sleep(1.0)"]
        record, consume = await runner.start(
            argv, tmp_path, workspace=tmp_path, stream_kind="command", provider="shell"
        )
        status_when_seen = None
        for _ in range(100):  # up to ~2s, well inside the child's 1s liveness
            await asyncio.sleep(0.02)
            events = event_bus.BUS.events_after(tmp_path, 0)
            if any("CHUNK" in (e.get("textDelta") or "") for e in events):
                status_when_seen = record.status
                break
        assert status_when_seen == "running", "delta must be visible before the process exits"
        await asyncio.wait_for(consume, timeout=5)
        events = event_bus.BUS.events_after(tmp_path, 0)
        assert any(e["type"] == "command.finished" for e in events), "completion is emitted once, after"

    asyncio.run(go())


def test_pillar3_secrets_never_reach_the_live_stream(tmp_path):
    """Pillar 3/Security: a token printed by a child is redacted in the streamed
    deltas — raw secrets must never be transported to the UI."""
    secret = "sk-" + "A" * 40

    async def go():
        runner = ProcessRunner()
        argv = [sys.executable, "-u", "-c", f"print('key={secret}', flush=True)"]
        _record, consume = await runner.start(
            argv, tmp_path, workspace=tmp_path, stream_kind="command", provider="shell"
        )
        await asyncio.wait_for(consume, timeout=5)

    asyncio.run(go())
    blob = str(event_bus.BUS.events_after(tmp_path, 0))
    assert secret not in blob
    assert "[REDACTED]" in blob
