"""Real subprocess runner: capture output, redact, cancel, write task logs."""

from __future__ import annotations

import asyncio
import os
import shlex
import signal
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, Optional

from .redaction import redact

MAX_CAPTURE_CHARS = 2_000_000  # per stream, in memory
LOG_BUFFER_MAX = 500


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class RunRecord:
    id: str
    argv: list[str]
    cwd: str
    task_id: Optional[str] = None
    step: Optional[str] = None
    provider: Optional[str] = None
    status: str = "running"  # running | succeeded | failed | cancelled | error
    exit_code: Optional[int] = None
    started_at: str = field(default_factory=now_iso)
    ended_at: Optional[str] = None
    duration_ms: Optional[int] = None
    stdout_parts: list[str] = field(default_factory=list)
    stderr_parts: list[str] = field(default_factory=list)
    truncated: bool = False
    log_file: Optional[str] = None
    pid: Optional[int] = None           # OS pid, for restart liveness checks
    prompt_file: Optional[str] = None   # durable prompt artifact, for the run ledger
    failure_kind: Optional[str] = None  # set on terminal non-success (see state_store)
    _start_monotonic: float = field(default_factory=time.monotonic)

    def to_ledger(self, workspace: "Path", tail: int = 4000) -> dict:
        """Durable, recovery-oriented projection (see docs 02 §Run). Output is tailed
        and redacted; full output stays in the per-run log file."""
        return {
            "id": self.id,
            "workspacePath": str(workspace),
            "commandPreview": self.command_preview(),
            "cwd": self.cwd,
            "provider": self.provider,
            "taskId": self.task_id,
            "step": self.step,
            "status": self.status,
            "pid": self.pid,
            "startedAt": self.started_at,
            "endedAt": self.ended_at,
            "durationMs": self.duration_ms,
            "exitCode": self.exit_code,
            "promptFile": self.prompt_file,
            "logFile": self.log_file,
            "stdoutTail": redact(self.stdout)[-tail:],
            "stderrTail": redact(self.stderr)[-tail:],
            "outputTruncated": self.truncated,
            "failureKind": self.failure_kind,
        }

    @property
    def stdout(self) -> str:
        return "".join(self.stdout_parts)

    @property
    def stderr(self) -> str:
        return "".join(self.stderr_parts)

    def command_preview(self) -> str:
        return redact(shlex.join(self.argv))

    def to_dict(self, output_tail: int = 20_000) -> dict:
        out = redact(self.stdout)
        err = redact(self.stderr)
        if output_tail and len(out) > output_tail:
            out = "…[truncated]…\n" + out[-output_tail:]
        if output_tail and len(err) > output_tail:
            err = "…[truncated]…\n" + err[-output_tail:]
        return {
            "id": self.id,
            "taskId": self.task_id,
            "step": self.step,
            "provider": self.provider,
            "status": self.status,
            "exitCode": self.exit_code,
            "startedAt": self.started_at,
            "endedAt": self.ended_at,
            "durationMs": self.duration_ms,
            "commandPreview": self.command_preview(),
            "cwd": self.cwd,
            "stdout": out,
            "stderr": err,
            "logFile": self.log_file,
        }


# Global, append-only (bounded) activity log shown on the Logs page.
LOG_BUFFER: list[dict] = []
_view_cleared_at: Optional[str] = None
_log_seq = 0


def add_log_entry(
    source: str,
    summary: str,
    *,
    provider: Optional[str] = None,
    task_id: Optional[str] = None,
    step: Optional[str] = None,
    status: str = "info",
    output: Optional[str] = None,
) -> None:
    global _log_seq
    _log_seq += 1
    entry = {
        "id": f"log-{_log_seq}",
        "time": now_iso(),
        "source": source,
        "provider": provider,
        "taskId": task_id,
        "step": step,
        "status": status,
        "summary": redact(summary)[:500],
        "output": redact(output or "")[-6000:] if output else "",
    }
    LOG_BUFFER.append(entry)
    if len(LOG_BUFFER) > LOG_BUFFER_MAX:
        del LOG_BUFFER[: len(LOG_BUFFER) - LOG_BUFFER_MAX]


def get_log_entries() -> list[dict]:
    if _view_cleared_at is None:
        return list(LOG_BUFFER)
    return [e for e in LOG_BUFFER if e["time"] > _view_cleared_at]


def clear_log_view() -> None:
    global _view_cleared_at
    _view_cleared_at = now_iso()


class ProcessRunner:
    """Runs real subprocesses; supports polling and cancellation by run id."""

    def __init__(self) -> None:
        self.runs: dict[str, RunRecord] = {}
        self.procs: dict[str, asyncio.subprocess.Process] = {}

    # ------------------------------------------------------------- helpers

    def _new_record(self, argv: list[str], cwd: Path, **meta) -> RunRecord:
        record = RunRecord(id=uuid.uuid4().hex[:12], argv=argv, cwd=str(cwd), **meta)
        self.runs[record.id] = record
        # Bound memory: keep only the most recent 100 finished runs.
        if len(self.runs) > 100:
            finished = [r for r in self.runs.values() if r.status != "running"]
            finished.sort(key=lambda r: r.started_at)
            for stale in finished[: len(self.runs) - 100]:
                self.runs.pop(stale.id, None)
        return record

    async def _read_stream(self, stream: asyncio.StreamReader, parts: list[str], record: RunRecord) -> None:
        captured = 0
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="replace")
            captured += len(text)
            if captured <= MAX_CAPTURE_CHARS:
                parts.append(text)
            elif not record.truncated:
                parts.append("\n[output truncated by AgentFlow]\n")
                record.truncated = True

    # Generic terminal-status -> failure-kind map. The orchestration layer may refine
    # this (e.g. provider_missing, policy_denied) before persisting to the run ledger.
    _FAILURE_KIND = {"failed": "exit_nonzero", "cancelled": "cancelled", "error": "start_error"}

    def _finalize(self, record: RunRecord, status: str, exit_code: Optional[int]) -> None:
        record.status = status
        record.exit_code = exit_code
        record.ended_at = now_iso()
        record.duration_ms = int((time.monotonic() - record._start_monotonic) * 1000)
        record.failure_kind = self._FAILURE_KIND.get(status)
        self.procs.pop(record.id, None)
        if record.log_file:
            self._write_log_file(record)

    def _write_log_file(self, record: RunRecord) -> None:
        try:
            path = Path(record.log_file)  # type: ignore[arg-type]
            path.parent.mkdir(parents=True, exist_ok=True)
            body = (
                f"# AgentFlow run {record.id}\n"
                f"# command: {record.command_preview()}\n"
                f"# cwd: {record.cwd}\n"
                f"# task: {record.task_id or '-'}  step: {record.step or '-'}  provider: {record.provider or '-'}\n"
                f"# started: {record.started_at}\n"
                f"# ended: {record.ended_at}\n"
                f"# status: {record.status}  exit: {record.exit_code}  duration_ms: {record.duration_ms}\n"
                f"\n--- STDOUT ---\n{redact(record.stdout)}\n"
                f"\n--- STDERR ---\n{redact(record.stderr)}\n"
            )
            path.write_text(body, encoding="utf-8")
        except OSError:
            pass  # logging must never crash a run

    # --------------------------------------------------------------- public

    async def run_and_wait(
        self,
        argv: list[str],
        cwd: Path,
        timeout: float = 30.0,
        **meta,
    ) -> RunRecord:
        """Run a quick command (probes, git) and wait for completion."""
        record, consume = await self.start(argv, cwd, **meta)
        if record.status == "error":
            return record
        try:
            await asyncio.wait_for(asyncio.shield(consume), timeout=timeout)
        except asyncio.TimeoutError:
            await self.cancel(record.id)
            try:
                await consume
            except asyncio.CancelledError:
                pass
            record.stderr_parts.append(f"\n[timed out after {timeout:.0f}s]\n")
        return record

    async def start(
        self,
        argv: list[str],
        cwd: Path,
        task_id: Optional[str] = None,
        step: Optional[str] = None,
        provider: Optional[str] = None,
        log_file: Optional[str] = None,
        on_complete: Optional[Callable[[RunRecord], Awaitable[None]]] = None,
    ) -> tuple[RunRecord, asyncio.Task]:
        """Start a process and return immediately; output is consumed in the background."""
        record = self._new_record(
            argv, cwd, task_id=task_id, step=step, provider=provider, log_file=log_file
        )
        # Children must not inherit OUR port assignment: dev servers honor PORT and
        # would bind on top of the AgentFlow backend, hijacking localhost:8787.
        child_env = {k: v for k, v in os.environ.items() if k not in ("PORT", "AGENTFLOW_PORT")}
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(cwd),
                env=child_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
                start_new_session=True,  # own process group -> clean cancellation
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            record.stderr_parts.append(f"failed to start: {exc}\n")
            self._finalize(record, "error", None)

            async def _noop() -> None:
                return None

            return record, asyncio.create_task(_noop())

        self.procs[record.id] = proc
        record.pid = proc.pid

        async def _consume() -> None:
            assert proc.stdout is not None and proc.stderr is not None
            await asyncio.gather(
                self._read_stream(proc.stdout, record.stdout_parts, record),
                self._read_stream(proc.stderr, record.stderr_parts, record),
            )
            code = await proc.wait()
            if record.status == "running":
                status = "succeeded" if code == 0 else "failed"
                if code is not None and code < 0:
                    status = "cancelled"
                self._finalize(record, status, code)
            else:  # cancel() already marked it
                record.exit_code = code
                if record.log_file:
                    self._write_log_file(record)
            if on_complete is not None:
                try:
                    await on_complete(record)
                except Exception as exc:  # noqa: BLE001 — never kill the loop
                    add_log_entry("system", f"on_complete hook failed: {exc}", status="error")

        return record, asyncio.create_task(_consume())

    async def cancel(self, run_id: str) -> bool:
        record = self.runs.get(run_id)
        proc = self.procs.get(run_id)
        if record is None or proc is None or proc.returncode is not None:
            return False
        record.status = "cancelled"
        record.failure_kind = "cancelled"
        record.ended_at = now_iso()
        record.duration_ms = int((time.monotonic() - record._start_monotonic) * 1000)
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass

        async def _hard_kill() -> None:
            await asyncio.sleep(4)
            if proc.returncode is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass

        asyncio.create_task(_hard_kill())
        self.procs.pop(run_id, None)
        return True

    async def cancel_all(self) -> list[str]:
        running = [rid for rid, p in list(self.procs.items()) if p.returncode is None]
        stopped = []
        for rid in running:
            if await self.cancel(rid):
                stopped.append(rid)
        return stopped

    def running_runs(self) -> list[RunRecord]:
        return [r for r in self.runs.values() if r.status == "running"]

    def running_for_provider(self, provider: str) -> Optional[RunRecord]:
        for record in self.running_runs():
            if record.provider == provider:
                return record
        return None

    def runs_for_task(self, task_id: str) -> list[RunRecord]:
        runs = [r for r in self.runs.values() if r.task_id == task_id]
        return sorted(runs, key=lambda r: r.started_at)


RUNNER = ProcessRunner()
