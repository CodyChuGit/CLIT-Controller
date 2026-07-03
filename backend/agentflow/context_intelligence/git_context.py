"""Git context via the existing async ``git_service`` (never shells out here).

Diffs come back already redacted by ``git_service``; this module only bounds
and packages them.
"""

from __future__ import annotations

from pathlib import Path

from .. import git_service
from .types import GitContext

MAX_DIFF_FILES = 10
MAX_DIFF_CHARS = 20_000


async def build_git_context(workspace_path: Path) -> GitContext:
    info = await git_service.git_info(workspace_path)
    if not info.get("isRepo"):
        return GitContext()

    changed: list[str] = list(info.get("changedFiles") or [])
    # Same refusal rule as the workspace reader: a tracked, modified .env would
    # otherwise flow into prompt previews/reports with only pattern-based
    # redaction between it and disk. Names may be listed; contents never.
    diffable = [p for p in changed if not (Path(p).name.startswith(".env") and Path(p).name != ".env.example")]
    parts: list[str] = []
    total = 0
    truncated = len(diffable) > MAX_DIFF_FILES
    for rel_path in diffable[:MAX_DIFF_FILES]:
        result = await git_service.file_diff(workspace_path, rel_path, staged=False)
        piece: str = result.get("diff", "")
        if result.get("truncated"):
            truncated = True
        if total + len(piece) > MAX_DIFF_CHARS:
            parts.append(f"[… diff for {rel_path} and later files elided]")
            truncated = True
            break
        parts.append(piece)
        total += len(piece)

    return GitContext(
        isRepo=True,
        branch=str(info.get("branch") or ""),
        changedFiles=changed,
        diff="\n".join(p for p in parts if p),
        truncated=truncated,
    )
