"""Live CLI terminals over WebSocket.

Output (server → client) is sent as raw binary frames; session lifecycle
metadata (launching/ready/closed) is sent as JSON text frames of the shape
{"type": "meta", "state": ..., "provider": ..., "executablePath": ...}.
Control (client → server) is sent as JSON text frames:
{"type": "input", "data": "..."}, {"type": "resize", "rows": N, "cols": N},
or {"type": "kill"}."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from .. import config
from ..origins import is_allowed_origin
from ..provider_probe import AGENT_PROVIDER_IDS, _definition, which
from ..terminal_service import CLOSED, TERMINALS, launch_command, session_key

router = APIRouter()

# WebSocket handshakes are not subject to CORS, so a malicious page the user
# visits could otherwise open ws://localhost:8787/.../ws and drive a real shell.
# Reject browser origins outside the app's own (shared allow-list — audit P3-39).
# A missing Origin (native clients, tests) is allowed.


@router.get("/status")
def terminals_status():
    """Which CLIs are installed (so the UI can label panes)."""
    return {
        "providers": AGENT_PROVIDER_IDS,
        "installed": {pid: which(pid) is not None for pid in AGENT_PROVIDER_IDS},
    }


@router.get("/{provider}/diagnostics")
def terminal_diagnostics(provider: str):
    """Why the pane is (or isn't) alive: resolved executable, session lifecycle
    state, and what to do about a failure — so the UI never shows a dead box
    with no explanation (revamp Workstream 3)."""
    if provider not in AGENT_PROVIDER_IDS:
        raise HTTPException(status_code=404, detail=f"unknown provider: {provider}")
    workspace = config.get_current_workspace()
    path = which(provider)
    session = TERMINALS.sessions.get(session_key(workspace, provider)) if workspace else None

    last_error = None
    if session is not None and session.exited:
        state = "closed"
        if session.exit_code not in (0, None):
            last_error = f"session exited with code {session.exit_code}"
    elif session is not None:
        state = session.state  # launching | ready
    elif path is None:
        state = "missing"
    else:
        state = "none"  # installed, no session yet

    suggested = None
    if path is None:
        suggested = _definition(provider).get("installHint")
    elif workspace is None:
        suggested = "Pick a workspace in Explorer first."
    elif state == "closed":
        suggested = "Restart the session."

    return {
        "provider": provider,
        "installed": path is not None,
        "executablePath": path,
        "workspace": str(workspace) if workspace else None,
        "sessionState": state,
        "lastLaunchError": last_error,
        "suggestedAction": suggested,
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
    if not is_allowed_origin(origin):
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
    session = await TERMINALS.get_or_create(
        key,
        str(workspace),
        launch_command(provider),
        provider=provider,
        executable_path=which(provider),
    )

    queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
    # Snapshot the scrollback and register for live output in one synchronous
    # step (no await between), then send the snapshot. Registering after an
    # `await ws.send_bytes(...)` would let the PTY reader append + broadcast bytes
    # during that await with no queue attached yet — those bytes would be missing
    # from both the snapshot and the live stream, leaving a gap on (re)connect.
    snapshot = bytes(session.buffer)
    session.clients.add(queue)
    if snapshot:
        await ws.send_bytes(snapshot)
    # Replay the current lifecycle state so a (re)connecting client knows whether
    # the CLI is still launching, ready, or already closed.
    await ws.send_text(json.dumps(session.current_meta()))
    # Force a TUI repaint for this attachment: the snapshot alone can render
    # blank when its paint history was addressed to a different/same-size grid.
    session.force_repaint()

    async def pump() -> None:
        try:
            while True:
                item = await queue.get()
                if item is CLOSED:
                    return
                # dict items are lifecycle metadata → JSON text frames; raw PTY
                # bytes stay binary for xterm.
                if isinstance(item, dict):
                    await ws.send_text(json.dumps(item))
                else:
                    await ws.send_bytes(item)
        except (WebSocketDisconnect, RuntimeError):
            return
        finally:
            # A dead pump must not leave a half-open socket: output stops but the
            # client's readyState stays OPEN, so it never auto-reconnects — a
            # frozen pane that still silently forwards keystrokes to the PTY.
            # Closing makes the client's onclose fire and the pane self-heal.
            try:
                await ws.close()
            except Exception:  # noqa: BLE001 — already closed/disconnected is fine
                pass

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
