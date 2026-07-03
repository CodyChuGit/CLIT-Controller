"""Optimization report persistence under ``<workspace>/.agentflow/context/``.

Report ids must match ``^[A-Za-z0-9_-]+$`` — validated on read BEFORE any
filesystem access (same path-traversal defense class as the SPA route).
Everything persisted passes ``redaction.redact_data`` first: the .env refusal
alone does not cover secrets inside logs or source files.
"""

from __future__ import annotations

import re
from pathlib import Path

from .. import config, paths
from ..redaction import redact_data
from .types import OptimizationReport

REPORT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def reports_dir(workspace_path: Path) -> Path:
    return paths.workspace_app_dir(workspace_path) / "context"


def save_report(workspace_path: Path, report: OptimizationReport) -> dict:
    """Persist the redacted report; returns the redacted dict (what callers may
    show or return — never the unredacted model)."""
    if not REPORT_ID_RE.match(report.id):
        raise ValueError(f"invalid report id: {report.id!r}")
    data = redact_data(report.model_dump())
    config.write_json(reports_dir(workspace_path) / f"{report.id}.json", data)
    return data


def load_report(workspace_path: Path, report_id: str) -> dict:
    """Load one persisted report. Raises ValueError on a malformed id (callers map
    it to 400) and FileNotFoundError when absent (callers map it to 404)."""
    if not REPORT_ID_RE.match(report_id or ""):
        raise ValueError("report id must match ^[A-Za-z0-9_-]+$")
    data = config.read_json(reports_dir(workspace_path) / f"{report_id}.json", None)
    if not isinstance(data, dict):
        raise FileNotFoundError(report_id)
    return data
