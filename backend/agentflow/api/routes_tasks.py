"""Tasks: creation, step execution, full sequence, logs, stop, open folder."""

from __future__ import annotations

import subprocess
import sys

from fastapi import APIRouter, HTTPException

from .. import paths, task_service
from ..models import RunFullRequest, RunStepRequest, StopRequest, TaskCreateRequest
from .routes_projects import require_workspace

router = APIRouter()


@router.get("")
def list_tasks():
    return task_service.list_tasks(require_workspace())


@router.post("")
def create_task(body: TaskCreateRequest):
    return task_service.create_task(require_workspace(), body.title.strip(), body.goal.strip())


@router.post("/stop")
async def stop(body: StopRequest):
    return await task_service.stop(body.runId)


@router.get("/{task_id}")
def get_task(task_id: str):
    try:
        return task_service.get_task_detail(require_workspace(), task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{task_id}/run/{step}")
async def run_step(task_id: str, step: str, body: RunStepRequest):
    try:
        return await task_service.run_step(require_workspace(), task_id, step, confirm=body.confirm)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{task_id}/run-full")
async def run_full(task_id: str, body: RunFullRequest):
    try:
        return await task_service.run_full_sequence(require_workspace(), task_id, confirm=body.confirm)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{task_id}/open-folder")
def open_folder(task_id: str):
    ws = require_workspace()
    folder = paths.task_dir(ws, task_id)
    if not folder.is_dir():
        raise HTTPException(status_code=404, detail="Task folder not found")
    if sys.platform != "darwin":
        raise HTTPException(status_code=400, detail="Open in Finder is only available on macOS.")
    subprocess.Popen(["open", str(folder)])
    return {"ok": True}


@router.get("/{task_id}/exchanges")
def task_exchanges(task_id: str):
    return {"steps": task_service.step_exchanges(require_workspace(), task_id)}


@router.get("/{task_id}/logs")
def task_logs(task_id: str):
    return {
        "files": task_service.list_task_logs(require_workspace(), task_id),
        "runs": [r.to_dict() for r in task_service.RUNNER.runs_for_task(task_id)],
    }


@router.get("/{task_id}/file")
def task_file(task_id: str, name: str):
    try:
        return task_service.read_task_file(require_workspace(), task_id, name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Not found: {exc}") from exc
