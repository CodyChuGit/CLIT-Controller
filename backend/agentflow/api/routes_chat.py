"""Chat with the orchestration model."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .. import chat_service
from .routes_projects import require_workspace

router = APIRouter()


class SendRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    provider: str | None = None


@router.get("")
def get_chat():
    return chat_service.chat_state(require_workspace())


@router.post("/send")
async def send(body: SendRequest):
    return await chat_service.send(require_workspace(), body.message.strip(), body.provider)


@router.post("/stop")
async def stop():
    return await chat_service.stop(require_workspace())


@router.post("/clear")
def clear():
    chat_service.clear_chat(require_workspace())
    return {"ok": True}
