"""Durable state surface: timeline events, run ledger, and approvals.

Additive endpoints over the new ``state_store`` ledgers. Existing polling endpoints
(`/api/logs`, `/api/queue`, task detail) are unchanged; these expose the durable record
that now survives restarts.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import chat_service, state_store
from .routes_projects import require_workspace

router = APIRouter()


@router.get("/events")
def events(cursor: int = 0, limit: int = 200):
    """Timeline events with id > cursor (polling fallback for the future SSE stream)."""
    ws = require_workspace()
    items = state_store.read_events(ws, after=cursor, limit=limit)
    return {"events": items, "cursor": state_store.events_cursor(ws)}


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
            ws, approval["action"], approval.get("provider") or "orchestrator",
            task_id=approval.get("taskId"), approved=True,
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
