"""Execute validated ControllerAction values — the authoritative mutation path.

Every mutation flows through the existing services (task / queue / policy /
approvals / process runner), so command classification and durable approval
gates keep applying exactly as before. This module only decides *which* service
call a validated action maps to, and reports what happened.

``chat_service`` is imported lazily inside helpers: it imports this package at
module load, and these handlers only run long after both modules exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .. import queue_service, state_store, task_service
from ..chat_directives import _normalize_steps
from ..controller_protocol import ControllerAction
from ..process_runner import RUNNER, now_iso

RETRYABLE = ("failed", "blocked", "skipped", "cancelled")


def _message(workspace: Path, provider: str, text: str) -> None:
    from .. import chat_service  # lazy: chat_service imports this package

    chat_service.append_message(workspace, "system", text, provider=provider)


def _task_event(workspace: Path, task_id: str, type_: str, detail: str, provider: Optional[str] = None) -> None:
    try:
        task_service._add_event(workspace, task_id, type_, detail, provider=provider)
    except FileNotFoundError:
        pass


def _slug(task_id: str) -> str:
    parts = task_id.split("-", 2)
    return parts[2] if len(parts) == 3 else task_id


def resolve_task(workspace: Path, ref: Optional[str], ctx_task_id: Optional[str]) -> Optional[str]:
    """A task id from an explicit ref ("latest", suffix, substring) or the turn's
    focused/consulted task. No ref and no context ⇒ None — never guess."""
    if not ref:
        return ctx_task_id
    tasks = task_service.list_tasks(workspace)
    if not tasks:
        return ctx_task_id
    if ref.lower() in ("latest", "last", "newest"):
        return tasks[0]["id"]
    for t in tasks:
        if t["id"] == ref or t["id"].endswith(ref) or ref in t["id"]:
            return t["id"]
    return ctx_task_id


class Outcome(dict):
    """{"actionType", "ok", "note", "mutated"} — plain dict with a constructor."""

    def __init__(self, action_type: str, ok: bool, note: str, mutated: bool):
        super().__init__(actionType=action_type, ok=ok, note=note, mutated=mutated)


async def execute(
    workspace: Path,
    action: ControllerAction,
    *,
    provider: str,
    source: str,
    task_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict:
    """Execute one validated ControllerAction and return an Outcome. Raising is
    reserved for programmer errors; expected failures come back ok=False."""
    kind = action.type

    if kind == "answer":
        return Outcome(kind, True, "answered", mutated=False)

    if kind == "create_task":
        meta = task_service.create_task(workspace, action.title[:200], action.goal, orchestrated=True)
        # Default to the planning step so a handed-over task always starts running;
        # the closed loop then consults the controller for what to do next.
        steps = _normalize_steps(action.steps) or ["codex_spec"]
        queue_service.add_steps(workspace, meta["id"], steps, source="orchestrator")
        note = f"Created “{action.title}” · queued {', '.join(steps)}"
        _message(workspace, provider, note)
        return Outcome(kind, True, note, mutated=True)

    if kind == "queue_steps":
        tid = resolve_task(workspace, action.taskId, task_id)
        steps = _normalize_steps(action.steps)
        if tid is None or steps is None:
            note = f"Couldn’t queue steps — no task matches `{action.taskId}`." if tid is None else "No valid steps to queue."
            _message(workspace, provider, note)
            return Outcome(kind, False, note, mutated=False)
        task_service.set_orchestrated(workspace, tid)
        queue_service.add_steps(workspace, tid, steps, source="orchestrator")
        note = f"Queued {', '.join(steps)} · {_slug(tid)}"
        _message(workspace, provider, note)
        return Outcome(kind, True, note, mutated=True)

    if kind == "run_command":
        from .. import chat_service  # lazy

        # Policy classification, approval gating and workspace confinement all
        # live in execute_run_directive — the action never bypasses them.
        await chat_service.execute_run_directive(workspace, action.command, provider, task_id=task_id)
        return Outcome(kind, True, f"ran `{action.command}` (policy-gated)", mutated=True)

    if kind == "request_approval":
        state_store.create_approval(
            workspace,
            action=action.command,
            kind="command",
            source="orchestrator",
            provider=provider,
            task_id=task_id,
            reason=action.reason,
        )
        note = f"Approval requested for `{action.command}`" + (f" — {action.reason}" if action.reason else "")
        _message(workspace, provider, note)
        if task_id:
            _task_event(workspace, task_id, "approval_required", note, provider=provider)
        return Outcome(kind, True, note, mutated=True)

    if kind == "request_user":
        if task_id:
            _task_event(workspace, task_id, "needs_user", f"controller needs your decision: {action.reason}", provider=provider)
        _message(workspace, provider, f"Needs your input — {action.reason}")
        return Outcome(kind, True, action.reason, mutated=bool(task_id))

    if kind == "retry":
        tid = resolve_task(workspace, action.taskId, task_id)
        data = queue_service.load_queue(workspace)
        candidates = [
            i
            for i in data["items"]
            if i["taskId"] == tid and (action.step is None or i["step"] == action.step) and i["status"] in RETRYABLE
        ]
        if not candidates:
            note = "Nothing to retry — no failed or blocked queue item matches."
            _message(workspace, provider, note)
            return Outcome(kind, False, note, mutated=False)
        item = candidates[-1]
        res = queue_service.retry_item(workspace, item["id"])
        ok = res.get("status") == "ok"
        note = f"Retrying {item['label']} ({item['provider']})" if ok else f"Retry failed: {res.get('message', res.get('status'))}"
        _message(workspace, provider, note)
        return Outcome(kind, ok, note, mutated=ok)

    if kind == "reroute":
        tid = resolve_task(workspace, action.taskId, task_id)
        data = queue_service.load_queue(workspace)
        candidates = [
            i for i in data["items"] if i["taskId"] == tid and i["step"] == action.step and i["status"] != "running"
        ]
        if not candidates:
            note = f"Nothing to reroute — no queue item for step `{action.step}`."
            _message(workspace, provider, note)
            return Outcome(kind, False, note, mutated=False)
        res = queue_service.reroute_item(workspace, candidates[-1]["id"], action.provider)
        ok = res.get("status") == "ok"
        note = (
            f"Rerouted {action.step} → {action.provider}"
            if ok
            else f"Reroute failed: {res.get('message', res.get('status'))}"
        )
        _message(workspace, provider, note)
        return Outcome(kind, ok, note, mutated=ok)

    if kind == "complete_task":
        tid = resolve_task(workspace, action.taskId, task_id)
        if tid is None:
            note = "Couldn’t complete — no task in scope."
            _message(workspace, provider, note)
            return Outcome(kind, False, note, mutated=False)
        reason = action.reason or "no reason given"
        meta = task_service._load_meta(workspace, tid)
        meta["status"] = "done"
        meta["orchestratorVerdict"] = {"verdict": "done", "reason": reason, "at": now_iso()}
        task_service._save_meta(workspace, meta)
        _task_event(workspace, tid, "done", f"controller declared the task complete: {reason}", provider=provider)
        state_store.append_event(
            workspace,
            "task.summary_ready",
            reason,
            task_id=tid,
            provider=provider,
            data={"status": "done", "verdict": "done"},
        )
        note = f"“{_slug(tid)}” complete — {reason}"
        _message(workspace, provider, note)
        return Outcome(kind, True, note, mutated=True)

    if kind == "cancel":
        if action.runId:
            ok = await RUNNER.cancel(action.runId)
            stopped = [action.runId] if ok else []
        else:
            stopped = await RUNNER.cancel_all()
        note = f"Cancelled {len(stopped)} run(s)."
        _message(workspace, provider, note)
        return Outcome(kind, True, note, mutated=bool(stopped))

    # Unreachable while the schema union and this dispatch stay in sync.
    return Outcome(kind, False, f"unhandled action type `{kind}`", mutated=False)
