"""Filesystem locations used by Command Line Interface Terminal Controller."""

from __future__ import annotations

from pathlib import Path

APP_DIR_NAME = ".agentflow"


def global_config_dir() -> Path:
    return Path.home() / APP_DIR_NAME


def global_config_file() -> Path:
    return global_config_dir() / "config.json"


def providers_cache_file() -> Path:
    return global_config_dir() / "providers.json"


def login_scripts_dir() -> Path:
    return global_config_dir() / "bin"


def terminals_run_dir() -> Path:
    """Per-run state for live PTY sessions (pidfiles used to reap orphans)."""
    return global_config_dir() / "run" / "terminals"


def repo_root() -> Path:
    # backend/agentflow/paths.py -> repo root
    return Path(__file__).resolve().parents[2]


def frontend_dist() -> Path:
    return repo_root() / "frontend" / "dist"


def workspace_app_dir(workspace: Path) -> Path:
    return workspace / APP_DIR_NAME


def workspace_config_file(workspace: Path) -> Path:
    return workspace_app_dir(workspace) / "config.json"


def usage_file(workspace: Path) -> Path:
    return workspace_app_dir(workspace) / "usage.json"


def tasks_dir(workspace: Path) -> Path:
    return workspace_app_dir(workspace) / "tasks"


def task_dir(workspace: Path, task_id: str) -> Path:
    return tasks_dir(workspace) / task_id


def task_logs_dir(workspace: Path, task_id: str) -> Path:
    return task_dir(workspace, task_id) / "logs"
