"""Execution queue: what the controller has cued up for each agent."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import queue_service
from .routes_projects import require_workspace

router = APIRouter()


class QueueAddRequest(BaseModel):
    taskId: str
    steps: list[str] = Field(min_length=1)


class QueueItemRequest(BaseModel):
    itemId: str


class QueueRerouteRequest(BaseModel):
    itemId: str
    provider: str


@router.get("")
def get_queue():
    return queue_service.queue_state(require_workspace())


@router.post("/add")
def add(body: QueueAddRequest):
    try:
        return queue_service.add_steps(require_workspace(), body.taskId, body.steps, source="user")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approve")
async def approve(body: QueueItemRequest):
    ws = require_workspace()
    result = await queue_service.approve_item(ws, body.itemId)
    return {**result, "queue": queue_service.queue_state(ws)}


@router.post("/remove")
def remove(body: QueueItemRequest):
    return queue_service.remove_item(require_workspace(), body.itemId)


@router.post("/clear")
def clear():
    return queue_service.clear_queue(require_workspace())


@router.post("/retry")
def retry(body: QueueItemRequest):
    return queue_service.retry_item(require_workspace(), body.itemId)


@router.post("/skip")
def skip(body: QueueItemRequest):
    return queue_service.skip_item(require_workspace(), body.itemId)


@router.post("/reroute")
def reroute(body: QueueRerouteRequest):
    return queue_service.reroute_item(require_workspace(), body.itemId, body.provider)
