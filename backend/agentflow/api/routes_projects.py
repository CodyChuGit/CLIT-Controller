"""Projects: workspace selection, file tree, file reading, git info, settings."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import config, git_service, headroom_service, paths, state_store
from .. import workspace as workspace_service
from ..models import (
    FileWriteRequest,
    GitCommitRequest,
    GitPathRequest,
    SettingsUpdateRequest,
    WorkspaceRequest,
)
from ..process_runner import add_log_entry

router = APIRouter()


def require_workspace() -> Path:
    ws = config.get_current_workspace()
    if ws is None:
        raise HTTPException(status_code=409, detail="No workspace selected. Set one on the Projects page.")
    return ws


@router.get("/current")
def current_project():
    ws = config.get_current_workspace()
    if ws is None:
        return {"workspacePath": None}
    return {
        "workspacePath": str(ws),
        "name": ws.name,
        "agentflowDir": str(paths.workspace_app_dir(ws)),
        "routing": config.get_workspace_routing(ws),
    }


@router.post("/workspace")
def set_workspace(body: WorkspaceRequest):
    try:
        cfg = config.set_workspace(body.path)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    add_log_entry("system", f"workspace set to {cfg['workspacePath']}")
    # Heal any state left running by a previous session for this workspace.
    try:
        state_store.recover_workspace(Path(cfg["workspacePath"]))
    except Exception as exc:  # noqa: BLE001 — recovery must not block workspace selection
        add_log_entry("system", f"recovery on workspace select failed: {exc}", status="error")
    return {"ok": True, "workspacePath": cfg["workspacePath"], "routing": cfg["routing"]}


@router.get("/tree")
def tree():
    return workspace_service.scan_tree(require_workspace())


@router.get("/file")
def read_file(path: str):
    try:
        return workspace_service.read_text_file(require_workspace(), path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"File not found: {exc}") from exc
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/file")
def write_file(body: FileWriteRequest):
    try:
        result = workspace_service.write_text_file(require_workspace(), body.path, body.content)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"File not found: {exc}") from exc
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    add_log_entry("system", f"saved {body.path} ({result['size']} bytes)")
    return result


@router.get("/git")
async def git():
    return await git_service.git_info(require_workspace())


@router.get("/git/diff")
async def git_diff():
    return await git_service.full_diff(require_workspace())


@router.get("/git/status")
async def git_status():
    return await git_service.status_files(require_workspace())


@router.get("/git/file-diff")
async def git_file_diff(path: str, staged: bool = False):
    return await git_service.file_diff(require_workspace(), path, staged)


@router.post("/git/stage")
async def git_stage(body: GitPathRequest):
    result = await git_service.stage(require_workspace(), body.path)
    add_log_entry("git", f"staged {body.path or 'all changes'}", provider="git")
    return result


@router.post("/git/unstage")
async def git_unstage(body: GitPathRequest):
    if not body.path:
        raise HTTPException(status_code=400, detail="path is required")
    result = await git_service.unstage(require_workspace(), body.path)
    add_log_entry("git", f"unstaged {body.path}", provider="git")
    return result


@router.post("/git/commit")
async def git_commit(body: GitCommitRequest):
    result = await git_service.commit(require_workspace(), body.message.strip())
    add_log_entry(
        "git",
        f"commit {'succeeded' if result['ok'] else 'failed'}: {body.message.strip()[:80]}",
        provider="git",
        status="info" if result["ok"] else "warn",
        output=result["output"],
    )
    return result


@router.post("/open-folder")
def open_folder():
    ws = require_workspace()
    if sys.platform != "darwin":
        raise HTTPException(status_code=400, detail="Open in Finder is only available on macOS.")
    subprocess.Popen(["open", str(ws)])
    return {"ok": True}


@router.get("/settings")
def get_settings():
    cfg = config.load_global_config()
    ws = config.get_current_workspace()
    return {
        "routing": cfg["routing"],
        "commandTemplates": cfg["commandTemplates"],
        "models": cfg["models"],
        "headroom": headroom_service.status(),
        "workspacePath": str(ws) if ws else None,
        "globalConfigPath": str(paths.global_config_file()),
        "workspaceConfigPath": str(paths.workspace_config_file(ws)) if ws else None,
        "usageFilePath": str(paths.usage_file(ws)) if ws else None,
    }


@router.post("/settings")
def save_settings(body: SettingsUpdateRequest):
    config.update_settings(
        routing=body.routing.model_dump() if body.routing else None,
        command_templates=body.commandTemplates,
        models=body.models,
        headroom=body.headroom,
    )
    add_log_entry("system", "settings updated (routing/command templates/models/headroom)")
    return get_settings()
