"""Live CLI terminals over WebSocket.

Output (server → client) is sent as raw binary frames. Control (client → server)
is sent as JSON text frames: {"type": "input", "data": "..."},
{"type": "resize", "rows": N, "cols": N}, or {"type": "kill"}."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import config
from ..provider_probe import AGENT_PROVIDER_IDS, which
from ..terminal_service import CLOSED, TERMINALS, launch_command, session_key

router = APIRouter()

# WebSocket handshakes are not subject to CORS, so a malicious page the user
# visits could otherwise open ws://localhost:8787/.../ws and drive a real shell.
# Reject browser origins outside the app's own. A missing Origin (native clients,
# tests) is allowed.
_ALLOWED_WS_ORIGINS = {
    "http://localhost:5180",
    "http://127.0.0.1:5180",
    "http://localhost:8787",
    "http://127.0.0.1:8787",
}


@router.get("/status")
def terminals_status():
    """Which CLIs are installed (so the UI can label panes)."""
    return {
        "providers": AGENT_PROVIDER_IDS,
        "installed": {pid: which(pid) is not None for pid in AGENT_PROVIDER_IDS},
    }


@router.post("/{provider}/kill")
async def terminal_kill(provider: str):
    """Kill a provider's session so the next connection starts a fresh one.
    Synchronous, so the UI can reliably restart without racing the socket."""
    workspace = config.get_current_workspace()
    if workspace is not None and provider in AGENT_PROVIDER_IDS:
        await TERMINALS.kill(session_key(workspace, provider))
    return {"ok": True}


@router.websocket("/{provider}/ws")
async def terminal_ws(ws: WebSocket, provider: str) -> None:
    origin = ws.headers.get("origin")
    if origin is not None and origin not in _ALLOWED_WS_ORIGINS:
        await ws.close(code=4403)
        return
    await ws.accept()
    if provider not in AGENT_PROVIDER_IDS:
        await ws.close(code=4404)
        return

    workspace = config.get_current_workspace()
    if workspace is None:
        await ws.send_bytes(b"\x1b[33mNo workspace selected. Pick one in Explorer.\x1b[0m\r\n")
        await ws.close()
        return

    key = session_key(workspace, provider)
    session = await TERMINALS.get_or_create(key, str(workspace), launch_command(provider))

    queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
    # Replay scrollback so a (re)connecting client sees the session so far.
    if session.buffer:
        await ws.send_bytes(bytes(session.buffer))
    session.clients.add(queue)

    async def pump() -> None:
        while True:
            item = await queue.get()
            if item is CLOSED:
                return
            try:
                await ws.send_bytes(item)
            except (WebSocketDisconnect, RuntimeError):
                return

    pump_task = asyncio.create_task(pump())
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            text = msg.get("text")
            data = msg.get("bytes")
            if data is not None:
                session.write(data)
            elif text is not None:
                try:
                    payload = json.loads(text)
                except ValueError:
                    session.write(text.encode())
                    continue
                kind = payload.get("type")
                if kind == "input":
                    session.write(str(payload.get("data", "")).encode())
                elif kind == "resize":
                    session.resize(int(payload.get("rows", 24)), int(payload.get("cols", 80)))
                elif kind == "kill":
                    await TERMINALS.kill(key)
                    break
    except WebSocketDisconnect:
        pass
    finally:
        session.clients.discard(queue)
        pump_task.cancel()
