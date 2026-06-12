"""Preview: run the workspace's dev server and report whether the app is reachable."""

from __future__ import annotations

import asyncio
import shlex
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config
from ..process_runner import RUNNER, add_log_entry
from ..redaction import redact
from .routes_projects import require_workspace

router = APIRouter()

DEFAULT_COMMAND = "npm run dev"
DEFAULT_URL = "http://localhost:5173"

# workspace path -> run id of its dev server
_servers: dict[str, str] = {}


class StartRequest(BaseModel):
    command: Optional[str] = None


class UrlRequest(BaseModel):
    url: str


def _state(ws) -> dict:
    run_id = _servers.get(str(ws))
    record = RUNNER.runs.get(run_id or "")
    running = record is not None and record.status == "running"
    if not running:
        _servers.pop(str(ws), None)
    return {
        "running": running,
        "runId": run_id if running else None,
        "command": config.get_workspace_setting(ws, "devCommand", DEFAULT_COMMAND),
        "url": config.get_workspace_setting(ws, "previewUrl", DEFAULT_URL),
        "output": redact((record.stdout + "\n" + record.stderr)[-3000:]) if record else "",
        "status": record.status if record else None,
        "exitCode": record.exit_code if record else None,
    }


@router.get("")
def get_preview():
    return _state(require_workspace())


@router.post("/url")
def set_url(body: UrlRequest):
    ws = require_workspace()
    host = urlparse(body.url).hostname
    if host not in ("localhost", "127.0.0.1"):
        raise HTTPException(status_code=400, detail="Preview URLs must point at localhost.")
    config.set_workspace_setting(ws, "previewUrl", body.url)
    return _state(ws)


@router.get("/check")
async def check():
    """TCP reachability of the preview URL (the iframe can't tell us itself)."""
    ws = require_workspace()
    url = config.get_workspace_setting(ws, "previewUrl", DEFAULT_URL)
    parsed = urlparse(url)
    host, port = parsed.hostname or "localhost", parsed.port or 80
    if host not in ("localhost", "127.0.0.1"):
        return {"ok": False, "detail": "localhost only"}
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=1.5)
        writer.close()
        return {"ok": True}
    except (OSError, asyncio.TimeoutError):
        return {"ok": False}


@router.post("/start")
async def start(body: StartRequest):
    ws = require_workspace()
    state = _state(ws)
    if state["running"]:
        return {"status": "already_running", **state}

    command = (body.command or state["command"]).strip()
    if not command:
        raise HTTPException(status_code=400, detail="No dev command configured.")
    config.set_workspace_setting(ws, "devCommand", command)

    argv = shlex.split(command)
    record, _task = await RUNNER.start(argv, ws, step="dev-server", provider="preview")
    if record.status == "error":
        return {"status": "error", "message": record.stderr.strip()[:300], **_state(ws)}

    _servers[str(ws)] = record.id
    add_log_entry("preview", f"dev server started: $ {command}", provider="preview")
    return {"status": "started", **_state(ws)}


@router.post("/stop")
async def stop():
    ws = require_workspace()
    run_id = _servers.pop(str(ws), None)
    stopped = await RUNNER.cancel(run_id) if run_id else False
    if stopped:
        add_log_entry("preview", "dev server stopped", provider="preview")
    return {"stopped": stopped, **_state(ws)}
