"""In-process, workspace-scoped event bus for live text streaming.

This is the single source for the live event stream consumed by
``GET /api/events`` (polling fallback) and ``GET /api/events/stream`` (SSE). Every
emitted event gets a process-monotonic ``id`` and lands in a bounded in-memory ring
buffer; readers resume by cursor (``id``) so a UI refresh/reconnect never duplicates
text.

Durability split (see docs/text-streaming-across-the-board.md §Backend Contract):
- Structural events (run/queue/task/approval lifecycle) are ALSO persisted to
  ``events.json`` by ``state_store.append_event`` for restart recovery; that helper
  mirrors them here so they stream live too.
- High-frequency text deltas are NOT persisted per-chunk (the full redacted run
  output is written to the run's log file on disk). They stream live and a refresh
  resumes from this buffer; a backend restart settles the run anyway (recovery).

Thread-safety: publishers run either on the event loop (async stream readers) or in
the FastAPI threadpool (sync route handlers), so id assignment + buffer append are
guarded by a lock. Redaction happens here too, as a defense-in-depth boundary —
secrets must never be persisted or broadcast (never redact in the browser).
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from .redaction import redact

MAX_BUFFER = 4000  # bounded ring buffer of recent events


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class EventBus:
    def __init__(self, maxlen: int = MAX_BUFFER) -> None:
        self._buf: "deque[dict]" = deque(maxlen=maxlen)
        self._seq = 0
        self._lock = threading.Lock()

    def publish(
        self,
        workspace: Union[str, Path, None],
        type_: str,
        *,
        detail: str = "",
        provider: Optional[str] = None,
        task_id: Optional[str] = None,
        run_id: Optional[str] = None,
        queue_item_id: Optional[str] = None,
        step: Optional[str] = None,
        sequence: Optional[int] = None,
        channel: Optional[str] = None,
        text_delta: Optional[str] = None,
        truncated: bool = False,
        data: Optional[dict] = None,
    ) -> dict:
        """Append one event to the live buffer and return it (with a monotonic id)."""
        red_detail = redact(detail) if detail else ""
        red_delta = redact(text_delta) if text_delta else text_delta
        now = _now_iso()
        with self._lock:
            self._seq += 1
            event = {
                "id": self._seq,
                "type": type_,
                "createdAt": now,
                "time": now,  # back-compat alias for existing consumers
                "workspacePath": str(workspace) if workspace else None,
                "provider": provider,
                "taskId": task_id,
                "runId": run_id,
                "queueItemId": queue_item_id,
                "step": step,
                "sequence": sequence,
                "channel": channel,
                "textDelta": red_delta,
                "redacted": True,
                "truncated": truncated,
                "detail": red_detail,
                "data": data or {},
            }
            self._buf.append(event)
        return event

    def events_after(
        self, workspace: Union[str, Path, None], after_id: int = 0, limit: Optional[int] = None
    ) -> list[dict]:
        """Events with ``id > after_id`` for this workspace, oldest first."""
        ws = str(workspace) if workspace else None
        with self._lock:
            items = [
                e
                for e in self._buf
                if e["id"] > after_id and (ws is None or e["workspacePath"] in (ws, None))
            ]
        if limit is not None:
            items = items[-limit:]
        return items

    def cursor(self) -> int:
        with self._lock:
            return self._seq


BUS = EventBus()
