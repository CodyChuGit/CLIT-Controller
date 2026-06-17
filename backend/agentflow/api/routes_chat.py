"""Chat with the traffic-control model."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import chat_service
from ..io_contracts import InputSubmission
from .routes_projects import require_workspace

router = APIRouter()


class SendRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    provider: str | None = None


class ChannelRequest(BaseModel):
    channel: str = chat_service.ORCHESTRATOR_CHANNEL


@router.get("")
def get_chat():
    return chat_service.chat_state(require_workspace())


@router.post("/send")
async def send(body: SendRequest):
    return await chat_service.send(require_workspace(), body.message.strip(), body.provider)


@router.post("/direct")
async def send_direct(body: SendRequest):
    if not body.provider:
        return {"status": "error", "message": "provider is required for direct chat"}
    return await chat_service.send_direct(require_workspace(), body.provider, body.message.strip())


@router.post("/submit")
async def submit(body: InputSubmission):
    """Typed input plane (I/O rebuild): one route for every input surface. FastAPI
    validates the InputSubmission (discriminated destination); destination + intent
    are explicit fields, never inferred from prose. Dispatches by destination —
    a task destination carries its taskId so 'continue this task' is actually
    scoped to that task (fixes the Tasks-continue bug)."""
    ws = require_workspace()
    text = body.content.text.strip()
    dest = body.destination
    if dest.kind == "provider":
        return await chat_service.send_direct(ws, dest.provider, text)
    if dest.kind == "task":
        return await chat_service.send(ws, text, focus_task_id=dest.taskId)
    if dest.kind == "controller":
        return await chat_service.send(ws, text)
    raise HTTPException(status_code=400, detail="unknown destination")


@router.post("/stop")
async def stop(body: ChannelRequest | None = None):
    channel = body.channel if body else chat_service.ORCHESTRATOR_CHANNEL
    return await chat_service.stop(require_workspace(), channel)


@router.post("/clear")
def clear(body: ChannelRequest | None = None):
    channel = body.channel if body else chat_service.ORCHESTRATOR_CHANNEL
    chat_service.clear_chat(require_workspace(), channel)
    return {"ok": True}
