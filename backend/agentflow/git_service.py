"""Local git: read-only checks plus explicit, user-triggered stage/commit."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .process_runner import RUNNER
from .redaction import redact

FULL_DIFF_LIMIT = 200_000  # chars

# porcelain XY codes shown in the UI ('?' is presented as U = untracked)
_BRANCH_RE = re.compile(r"## (\S+?)(?:\.\.\.(\S+))?(?: \[(.+)\])?$")


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


# ---------------------------------------------------- VS Code-style source control


def parse_porcelain(out: str) -> dict:
    """Parse `git status --porcelain=v1 --branch` into staged/unstaged groups."""
    branch, upstream, ahead, behind = None, None, 0, 0
    staged: list[dict] = []
    changes: list[dict] = []
    for line in out.splitlines():
        if line.startswith("## "):
            m = _BRANCH_RE.match(line)
            if m:
                branch, upstream = m.group(1), m.group(2)
                for part in (m.group(3) or "").split(", "):
                    if part.startswith("ahead "):
                        ahead = int(part[6:])
                    elif part.startswith("behind "):
                        behind = int(part[7:])
            else:
                branch = line[3:]
            continue
        if len(line) < 4:
            continue
        x, y, path = line[0], line[1], line[3:]
        if " -> " in path:  # renames: show the new name
            path = path.split(" -> ", 1)[1]
        if x == "?":
            changes.append({"path": path, "code": "U"})
            continue
        if x not in (" ",):
            staged.append({"path": path, "code": x})
        if y not in (" ",):
            changes.append({"path": path, "code": y})
    return {
        "branch": branch,
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "staged": staged,
        "changes": changes,
    }


async def status_files(workspace: Path) -> dict:
    """Per-file working-tree state for the Source Control panel."""
    if shutil.which("git") is None:
        return {"installed": False, "isRepo": False}
    code, out = await _git(workspace, "status", "--porcelain=v1", "--branch")
    if code != 0:
        return {"installed": True, "isRepo": False}
    parsed = parse_porcelain(out)
    parsed.update({"installed": True, "isRepo": True})
    return parsed


async def file_diff(workspace: Path, rel_path: str, staged: bool) -> dict:
    """Diff for one file; untracked files are rendered as all-added lines."""
    if staged:
        code, out = await _git(workspace, "diff", "--cached", "--", rel_path)
    else:
        code, out = await _git(workspace, "diff", "--", rel_path)

    if code == 0 and not out.strip():
        # Probably untracked — synthesize an all-added view.
        target = (workspace / rel_path).resolve()
        # Mirror the workspace read guard: never surface .env contents via the
        # untracked-file synthesis path (audit P2-22). redact() below is
        # defense-in-depth, not the primary control.
        if target.name.startswith(".env") and target.name != ".env.example":
            return {"path": rel_path, "staged": staged, "diff": "(.env files are not shown)", "truncated": False}
        if target.is_relative_to(workspace.resolve()) and target.is_file():
            try:
                raw = target.read_bytes()[:FULL_DIFF_LIMIT]
                if b"\x00" not in raw[:8192]:
                    body = raw.decode("utf-8", errors="replace")
                    out = f"diff --git a/{rel_path} b/{rel_path}\nnew file (untracked)\n+++ b/{rel_path}\n" + "".join(
                        f"+{line}\n" for line in body.splitlines()
                    )
                else:
                    out = f"(binary file: {rel_path})"
            except OSError as exc:
                out = f"(could not read {rel_path}: {exc})"

    truncated = len(out) > FULL_DIFF_LIMIT
    if truncated:
        out = out[:FULL_DIFF_LIMIT] + "\n…[diff truncated]…"
    return {"path": rel_path, "staged": staged, "diff": redact(out), "truncated": truncated}


async def stage(workspace: Path, rel_path: str | None) -> dict:
    """git add — explicit user action from the Source Control panel."""
    args = ["add", "-A"] if rel_path is None else ["add", "--", rel_path]
    code, out = await _git(workspace, *args)
    return {"ok": code == 0, "output": redact(out)}


async def unstage(workspace: Path, rel_path: str) -> dict:
    code, out = await _git(workspace, "reset", "HEAD", "--", rel_path)
    return {"ok": code == 0, "output": redact(out)}


async def commit(workspace: Path, message: str) -> dict:
    """git commit — explicit user action; never called automatically."""
    code, out = await _git(workspace, "commit", "-m", message)
    return {"ok": code == 0, "output": redact(out)[-2000:]}
