"""Local git checks (read-only; never mutates the repo)."""

from __future__ import annotations

import shutil
from pathlib import Path

from .process_runner import RUNNER
from .redaction import redact

FULL_DIFF_LIMIT = 200_000  # chars


async def _git(workspace: Path, *args: str, timeout: float = 20) -> tuple[int, str]:
    rec = await RUNNER.run_and_wait(["git", *args], workspace, timeout=timeout, provider="git")
    out = rec.stdout.strip() or rec.stderr.strip()
    return (rec.exit_code if rec.exit_code is not None else -1), out


async def git_info(workspace: Path) -> dict:
    if shutil.which("git") is None:
        return {"installed": False, "isRepo": False, "error": "git is not installed"}

    code, _ = await _git(workspace, "rev-parse", "--is-inside-work-tree")
    if code != 0:
        return {"installed": True, "isRepo": False, "error": "Not a git repository"}

    _, branch = await _git(workspace, "rev-parse", "--abbrev-ref", "HEAD")
    _, status_short = await _git(workspace, "status", "--short")
    _, diff_stat = await _git(workspace, "diff", "--stat")
    _, names = await _git(workspace, "diff", "--name-only")
    changed = [line for line in names.splitlines() if line.strip()]

    return {
        "installed": True,
        "isRepo": True,
        "branch": branch or "(detached)",
        "statusShort": redact(status_short),
        "diffStat": redact(diff_stat),
        "changedFiles": changed,
        "changedFileCount": len(changed),
    }


async def full_diff(workspace: Path) -> dict:
    code, out = await _git(workspace, "diff")
    truncated = len(out) > FULL_DIFF_LIMIT
    if truncated:
        out = out[:FULL_DIFF_LIMIT] + "\n…[diff truncated]…"
    return {"ok": code == 0, "diff": redact(out), "truncated": truncated}


async def diff_size(workspace: Path) -> int:
    """Approximate change size in diff characters (0 when not a repo)."""
    code, out = await _git(workspace, "diff", "--stat")
    return len(out) if code == 0 else 0
