"""Characterization tests for process cancellation and timeout reaping.

The SIGTERM->SIGKILL escalation in ProcessRunner.cancel and the timeout branch in
run_and_wait are the control paths that keep hung/abandoned agent process groups
from leaking. They were previously exercised only on the happy path; these tests
pin the reaping behaviour (see audit finding P1-11). Each test uses a fresh
ProcessRunner for isolation, mirroring test_redaction/test_streaming.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

from agentflow.process_runner import ProcessRunner

SLEEP = [sys.executable, "-c", "import time; time.sleep(30)"]


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:  # exists but reused by another owner — treat as alive
        return True


def _wait_gone(pid: int, timeout: float = 6.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.05)
    return not _alive(pid)


def test_cancel_terminates_running_process(tmp_path):
    async def go():
        runner = ProcessRunner()
        record, consume = await runner.start(SLEEP, tmp_path)
        assert record.status == "running"
        pid = record.pid
        assert pid is not None
        assert await runner.cancel(record.id) is True
        assert record.status == "cancelled"
        assert record.failure_kind == "cancelled"
        await asyncio.wait_for(consume, timeout=10)  # let _consume observe exit
        return pid

    pid = asyncio.run(go())
    assert _wait_gone(pid), "cancelled process group should be reaped"


def test_run_and_wait_times_out_and_reaps(tmp_path):
    async def go():
        runner = ProcessRunner()
        record = await runner.run_and_wait(SLEEP, tmp_path, timeout=0.3)
        return record

    record = asyncio.run(go())
    assert "timed out" in record.stderr.lower()
    assert record.pid is not None
    assert _wait_gone(record.pid), "timed-out process group should be reaped"


def test_cancel_all_returns_running_run_ids(tmp_path):
    async def go():
        runner = ProcessRunner()
        r1, c1 = await runner.start(SLEEP, tmp_path)
        r2, c2 = await runner.start(SLEEP, tmp_path)
        stopped = await runner.cancel_all()
        await asyncio.gather(c1, c2)
        return set(stopped), {r1.id, r2.id}, [r1.pid, r2.pid]

    stopped, ids, pids = asyncio.run(go())
    assert stopped == ids
    for pid in pids:
        assert _wait_gone(pid)


def test_start_failure_records_error_status(tmp_path):
    """A nonexistent binary fails to start and is recorded as error, not running."""

    async def go():
        runner = ProcessRunner()
        record, consume = await runner.start(["definitely-not-a-real-binary-xyz"], tmp_path)
        await consume
        return record

    record = asyncio.run(go())
    assert record.status == "error"
    assert record.exit_code is None
