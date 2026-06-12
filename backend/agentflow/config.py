"""Global (~/.agentflow) and per-workspace (.agentflow/) configuration."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from . import paths

DEFAULT_ROUTING = {
    "orchestrator": "antigravity",
    "pm": "codex",
    "engineer": "claude",
    "qa": "antigravity",
}

# {prompt} is replaced with the generated prompt as a single argv element
# (parsed with shlex, never interpolated into a shell string).
# {model} expands to `--model <configured model>` or disappears when unset.
# Note: for agy, {model} must come before -p because -p takes the prompt as its value.
DEFAULT_COMMAND_TEMPLATES = {
    # --skip-git-repo-check: workspaces aren't always git repos (the user picked the
    # folder deliberately). --sandbox workspace-write: codex must be able to write the
    # handoff files; writes stay inside the workspace.
    "codex": "codex exec --skip-git-repo-check --sandbox workspace-write {model} {prompt}",
    # acceptEdits: claude may write/edit files without interactive approval (required in
    # headless -p mode); shell commands still follow normal permission rules.
    "claude": "claude -p --permission-mode acceptEdits {model} {prompt}",
    # --sandbox: agy's own terminal-restriction sandbox keeps it inside the workspace.
    "antigravity": "agy --sandbox {model} -p {prompt}",
}

# Previous defaults we upgrade automatically when seen in stored config.
_STALE_TEMPLATES = {
    "codex": {"codex exec {prompt}", "codex exec {model} {prompt}"},
    "claude": {"claude -p {prompt}", "claude -p {model} {prompt}"},
    "antigravity": {"antigravity {prompt}", "antigravity -p {prompt}", "agy -p {prompt}", "agy {model} -p {prompt}"},
}


def _migrate_gemini(routing: dict) -> dict:
    """Gemini CLI is sunset; Antigravity CLI replaced it. Map old configs forward."""
    return {role: ("antigravity" if provider == "gemini" else provider) for role, provider in routing.items()}


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, data: Any) -> None:
    """Atomic JSON write (tmp file + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ---------------------------------------------------------------- global config


def load_global_config() -> dict:
    cfg = read_json(paths.global_config_file(), {}) or {}
    cfg.setdefault("currentWorkspace", None)
    cfg.setdefault("routing", dict(DEFAULT_ROUTING))
    cfg["routing"] = _migrate_gemini(cfg["routing"])
    templates = dict(DEFAULT_COMMAND_TEMPLATES)
    templates.update(cfg.get("commandTemplates") or {})
    templates.pop("gemini", None)
    for pid, stale in _STALE_TEMPLATES.items():
        if templates.get(pid) in stale:
            templates[pid] = DEFAULT_COMMAND_TEMPLATES[pid]
    cfg["commandTemplates"] = templates
    cfg.setdefault("models", {})  # provider id -> model name ("" = CLI default)
    return cfg


def save_global_config(cfg: dict) -> None:
    write_json(paths.global_config_file(), cfg)


def get_current_workspace() -> Optional[Path]:
    raw = load_global_config().get("currentWorkspace")
    if not raw:
        return None
    p = Path(raw).expanduser()
    return p if p.is_dir() else None


def get_command_templates() -> dict[str, str]:
    return load_global_config()["commandTemplates"]


def get_models() -> dict[str, str]:
    return load_global_config()["models"]


def update_settings(
    routing: Optional[dict] = None,
    command_templates: Optional[dict] = None,
    models: Optional[dict] = None,
) -> dict:
    cfg = load_global_config()
    if routing:
        cfg["routing"] = {**cfg["routing"], **routing}
        ws = get_current_workspace()
        if ws is not None:
            ws_cfg = read_json(paths.workspace_config_file(ws), {}) or {}
            ws_cfg["routing"] = cfg["routing"]
            ws_cfg["workspacePath"] = str(ws)
            write_json(paths.workspace_config_file(ws), ws_cfg)
    if command_templates:
        cfg["commandTemplates"] = {**cfg["commandTemplates"], **command_templates}
    if models is not None:
        merged = {**cfg["models"], **models}
        cfg["models"] = {pid: m.strip() for pid, m in merged.items() if m and m.strip()}
    save_global_config(cfg)
    return cfg


# ------------------------------------------------------------- workspace config


def ensure_workspace(workspace: Path) -> dict:
    """Create <workspace>/.agentflow/{config.json, usage.json, tasks/}; return workspace config."""
    workspace = workspace.expanduser().resolve()
    if not workspace.is_dir():
        raise FileNotFoundError(f"Not a directory: {workspace}")

    app_dir = paths.workspace_app_dir(workspace)
    app_dir.mkdir(parents=True, exist_ok=True)
    paths.tasks_dir(workspace).mkdir(parents=True, exist_ok=True)

    # Keep the .agentflow directory out of the user's repo without touching
    # the repo's own .gitignore.
    self_ignore = app_dir / ".gitignore"
    if not self_ignore.exists():
        self_ignore.write_text("*\n", encoding="utf-8")

    cfg_file = paths.workspace_config_file(workspace)
    cfg = read_json(cfg_file, None)
    if cfg is None:
        cfg = {
            "workspacePath": str(workspace),
            "routing": dict(load_global_config()["routing"]),
        }
        write_json(cfg_file, cfg)

    # usage.json is created by usage_service on first access; do it here too so
    # selecting a workspace immediately materializes all expected files.
    from . import usage_service

    usage_service.ensure_usage(workspace)
    return cfg


def set_workspace(path_str: str) -> dict:
    workspace = Path(path_str).expanduser().resolve()
    cfg = ensure_workspace(workspace)
    g = load_global_config()
    g["currentWorkspace"] = str(workspace)
    save_global_config(g)
    return cfg


def get_workspace_setting(workspace: Path, key: str, default):
    cfg = read_json(paths.workspace_config_file(workspace), {}) or {}
    return cfg.get(key, default)


def set_workspace_setting(workspace: Path, key: str, value) -> None:
    cfg = read_json(paths.workspace_config_file(workspace), {}) or {}
    cfg[key] = value
    cfg.setdefault("workspacePath", str(workspace))
    write_json(paths.workspace_config_file(workspace), cfg)


def get_workspace_routing(workspace: Path) -> dict:
    cfg = read_json(paths.workspace_config_file(workspace), {}) or {}
    routing = dict(DEFAULT_ROUTING)
    routing.update(cfg.get("routing") or {})
    return _migrate_gemini(routing)
