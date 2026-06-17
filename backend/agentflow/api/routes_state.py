"""Durable state surface: timeline events, run ledger, and approvals.

Additive endpoints over the new ``state_store`` ledgers. Existing polling endpoints
(`/api/logs`, `/api/queue`, task detail) are unchanged; these expose the durable record
that now survives restarts.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from .. import chat_service, event_bus, state_store
from .routes_projects import require_workspace

router = APIRouter()


@router.get("/events")
def events(cursor: int = 0, limit: int = 500):
    """Live events with id > cursor (polling fallback for the SSE stream).

    Reads the in-memory event bus so the same stream — including text deltas —
    is available when SSE is unavailable. Dedupe by ``id`` on the client.
    """
    ws = require_workspace()
    items = event_bus.BUS.events_after(ws, after_id=cursor, limit=limit)
    return {"events": items, "cursor": event_bus.BUS.cursor()}


@router.get("/events/stream")
async def events_stream(request: Request, cursor: int = 0):
    """Server-Sent Events stream of live workspace events, resumable by cursor.

    On reconnect the browser sends ``Last-Event-ID``; we honor it so streamed text
    is never duplicated. Heartbeat comments keep the connection alive.
    """
    ws = require_workspace()
    try:
        last = max(int(cursor), int(request.headers.get("last-event-id", 0)))
    except (TypeError, ValueError):
        last = int(cursor)

    async def gen():
        nonlocal last
        idle = 0
        while True:
            if await request.is_disconnected():
                break
            items = event_bus.BUS.events_after(ws, after_id=last, limit=1000)
            if items:
                idle = 0
                for e in items:
                    last = e["id"]
                    # No `event:` line — the browser's EventSource.onmessage then
                    # receives every event; the type lives in the JSON payload.
                    yield f"id: {e['id']}\ndata: {json.dumps(e)}\n\n"
            else:
                idle += 1
                if idle >= 20:  # ~5s of quiet -> keep-alive comment
                    idle = 0
                    yield ": ping\n\n"
            await asyncio.sleep(0.25)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    run = state_store.get_run(require_workspace(), run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    return run


@router.get("/approvals")
def list_approvals(pendingOnly: bool = False):
    return {"approvals": state_store.list_approvals(require_workspace(), pending_only=pendingOnly)}


@router.post("/approvals/{approval_id}/approve")
async def approve(approval_id: str):
    ws = require_workspace()
    approval = state_store.get_approval(ws, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail=f"approval not found: {approval_id}")
    if approval["status"] != "pending":
        return {"status": approval["status"], "approval": approval}
    resolved = state_store.resolve_approval(ws, approval_id, approved=True, resolver="user")
    # Execute the now-authorized command (hard denials still apply inside).
    if approval.get("kind") == "command":
        await chat_service.execute_run_directive(
            ws,
            approval["action"],
            approval.get("provider") or "orchestrator",
            task_id=approval.get("taskId"),
            approved=True,
        )
    return {"status": "approved", "approval": resolved}


@router.post("/approvals/{approval_id}/reject")
def reject(approval_id: str):
    ws = require_workspace()
    approval = state_store.get_approval(ws, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail=f"approval not found: {approval_id}")
    resolved = state_store.resolve_approval(ws, approval_id, approved=False, resolver="user")
    return {"status": "rejected", "approval": resolved}
