"""Projects: workspace selection, file tree, file reading, git info, settings."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import config, git_service, paths, workspace as workspace_service
from ..models import SettingsUpdateRequest, WorkspaceRequest
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
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    add_log_entry("system", f"workspace set to {cfg['workspacePath']}")
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


@router.get("/git")
async def git():
    return await git_service.git_info(require_workspace())


@router.get("/git/diff")
async def git_diff():
    return await git_service.full_diff(require_workspace())


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
    )
    add_log_entry("system", "settings updated (routing/command templates)")
    return get_settings()
