"""Terminal/log context from the two sanctioned sources only.

- ``process_runner.get_log_entries()`` — the bounded, already-redacted buffer.
- Recent ``RUNNER.runs`` records via their ``to_dict()`` tails.

PTY terminal scrollback is deliberately NOT read: it is raw ANSI bytes and the
backend has no ANSI stripper (only the frontend does).
"""

from __future__ import annotations

from ..process_runner import RUNNER, get_log_entries
from .types import LogContext

MAX_LOG_ENTRIES = 30
MAX_RUN_RECORDS = 3
RUN_TAIL_CHARS = 1500


def build_log_context() -> LogContext:
    lines: list[str] = []
    sources: list[str] = []

    entries = get_log_entries()[-MAX_LOG_ENTRIES:]
    if entries:
        sources.append("activity_log")
        errors = [e for e in entries if e.get("status") in ("warn", "error")]
        lines.append(f"Recent activity: {len(entries)} entries, {len(errors)} warn/error.")
        for entry in entries[-10:]:
            lines.append(f"[{entry['time']}] {entry['source']} {entry['status']}: {entry['summary']}")

    runs = sorted(RUNNER.runs.values(), key=lambda r: r.started_at)[-MAX_RUN_RECORDS:]
    if runs:
        sources.append("run_records")
        for record in runs:
            d = record.to_dict(output_tail=RUN_TAIL_CHARS)
            lines.append(
                f"Run {d['id']} ({d['provider'] or '-'}/{d['step'] or '-'}): {d['status']}"
                + (f" exit {d['exitCode']}" if d["exitCode"] is not None else "")
            )
            tail = (d["stdout"] or d["stderr"]).strip()
            if tail:
                lines.extend(tail.splitlines()[-8:])

    return LogContext(summary="\n".join(lines), entryCount=len(entries), sources=sources)
