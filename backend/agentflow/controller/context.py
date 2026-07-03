"""Prompt-context builders for controller turns (moved out of chat_service)."""

from __future__ import annotations

from pathlib import Path

from .. import git_service, headroom_service, queue_service, task_service, usage_service


async def workspace_summary(workspace: Path) -> str:
    git = await git_service.git_info(workspace)
    if git.get("isRepo"):
        git_line = f"branch {git.get('branch')}, {git.get('changedFileCount', 0)} changed files"
    else:
        git_line = "not a git repository"
    tasks = task_service.list_tasks(workspace)[:5]
    task_lines = "".join(f"\n- {t['id']}: {t['title']} ({t['status']})" for t in tasks) or " none yet"
    # The controller must see what each agent actually did, not just task names —
    # crushed in-process by Headroom when it grows bulky (fail-open: unchanged).
    detail = "\n\n".join(task_service.task_state_summary(workspace, t["id"]) for t in tasks[:2])
    detail = await headroom_service.compress_context(
        detail, instructions="Current task state per agent — keep statuses, steps, blockers, artifacts."
    )
    live_line = usage_service.live_summary_line()
    return (
        f"Workspace: {workspace} ({git_line})\n"
        f"{queue_service.summary_line(workspace)}\n"
        + (f"{live_line}\n" if live_line else "")
        + f"Recent CLITC tasks:{task_lines}"
        + (f"\n\nCurrent task state (per agent):\n{detail}" if detail else "")
    )


def focus_task_brief(workspace: Path, task_id: str) -> str:
    """Explicit one-block context for a task-scoped submission (Input plane). Keeps
    the user's stored message clean while telling the controller which task to
    continue — context is structured prompt input, never buried in the user text."""
    try:
        meta = task_service._load_meta(workspace, task_id)
    except FileNotFoundError:
        return f"Focused task: {task_id} (not found)."
    return (
        f"FOCUSED TASK (continue this task): {meta.get('id', task_id)} — "
        f"{meta.get('title', '(untitled)')} [status: {meta.get('status', 'unknown')}]. "
        f"Goal: {meta.get('goal', '')}".strip()
    )
