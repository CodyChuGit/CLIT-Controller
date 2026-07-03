"""Execution queue: the controller enqueues steps, the system cues each agent.

One step per agent at a time, queue order preserved within a task. Items live in
<workspace>/.agentflow/queue.json so the queue survives restarts.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Optional

from . import config, paths, provider_probe, state_store, task_service, transitions, usage_service
from .config import read_json, write_json
from .process_runner import RUNNER, add_log_entry, now_iso

ACTIVE_STATUSES = ("queued", "awaiting_approval", "blocked", "running")
TERMINAL_KEEP = 20  # finished items kept for the history view

TICK_SECONDS = 1.5


def _queue_file(workspace: Path) -> Path:
    return paths.workspace_app_dir(workspace) / "queue.json"


def load_queue(workspace: Path) -> dict:
    data = read_json(_queue_file(workspace), None)
    if not isinstance(data, dict) or "items" not in data:
        data = {"items": []}
    return data


def _save(workspace: Path, data: dict) -> None:
    data["updatedAt"] = now_iso()
    write_json(_queue_file(workspace), data)


def queue_state(workspace: Path) -> dict:
    data = load_queue(workspace)
    usage = usage_service.ensure_usage(workspace)
    return {
        "items": data["items"],
        "mode": usage.get("orchestrationMode", "balanced"),
        "activeCount": sum(1 for i in data["items"] if i["status"] in ACTIVE_STATUSES),
        "runningProviders": sorted({r.provider for r in RUNNER.running_runs() if r.provider}),
    }


def summary_line(workspace: Path) -> str:
    """Compact queue summary for the controller's context."""
    items = load_queue(workspace)["items"]
    active = [i for i in items if i["status"] in ACTIVE_STATUSES]
    if not active:
        return "Queue: empty"
    running = [i for i in active if i["status"] == "running"]
    parts = [f"Queue: {len(active)} active"]
    if running:
        r = running[0]
        parts.append(f"running: {r['step']}→{r['provider']} ({r['taskId']})")
    nxt = next((i for i in active if i["status"] in ("queued", "awaiting_approval")), None)
    if nxt:
        parts.append(f"next: {nxt['step']}→{nxt['provider']} ({nxt['taskId']})")
    return "; ".join(parts)


# ----------------------------------------------------------------- mutations


def add_steps(workspace: Path, task_id: str, steps: list[str], source: str = "orchestrator") -> dict:
    """Enqueue steps for a task (validates task + step names, skips active duplicates)."""
    task_service._load_meta(workspace, task_id)  # raises FileNotFoundError for bad ids
    bad = [s for s in steps if s not in task_service.STEP_DEFS]
    if bad:
        raise ValueError(f"unknown step(s): {', '.join(bad)}")

    data = load_queue(workspace)
    active = {(i["taskId"], i["step"]) for i in data["items"] if i["status"] in ACTIVE_STATUSES}
    added: list[dict[str, Any]] = []
    for step in steps:
        if (task_id, step) in active:
            continue
        item: dict[str, Any] = {
            "id": uuid.uuid4().hex[:8],
            "taskId": task_id,
            "step": step,
            "label": task_service.STEP_DEFS[step]["label"],
            "provider": task_service.step_provider(workspace, step),
            "status": "queued",
            "source": source,
            "enqueuedAt": now_iso(),
            "note": None,
            "runId": None,
            "attempt": 1,
            "providerOverride": None,
        }
        data["items"].append(item)
        added.append(item)

    if added:
        _save(workspace, data)
        labels = ", ".join(f"{i['label']}→{i['provider']}" for i in added)
        task_service._add_event(
            workspace,
            task_id,
            "queued",
            f"{source} queued {len(added)} step(s): {labels} — the system will cue each agent in order",
        )
        for i in added:
            state_store.append_event(
                workspace,
                "queue.enqueued",
                f"queued {i['label']} → {i['provider']}",
                task_id=task_id,
                step=i["step"],
                provider=i["provider"],
                data={"itemId": i["id"], "source": source},
            )
        add_log_entry("queue", f"queued {len(added)} step(s) for {task_id}: {labels}", task_id=task_id)
    return queue_state(workspace)


def remove_item(workspace: Path, item_id: str) -> dict:
    data = load_queue(workspace)
    data["items"] = [i for i in data["items"] if not (i["id"] == item_id and i["status"] != "running")]
    _save(workspace, data)
    return queue_state(workspace)


def clear_queue(workspace: Path) -> dict:
    data = load_queue(workspace)
    data["items"] = [i for i in data["items"] if i["status"] == "running"]
    _save(workspace, data)
    add_log_entry("queue", "queue cleared")
    return queue_state(workspace)


def _set_item(workspace: Path, item_id: str, **fields) -> Optional[dict]:
    data = load_queue(workspace)
    for item in data["items"]:
        if item["id"] == item_id:
            _apply_status(workspace, item, fields)
            item.update(fields)
            _save(workspace, data)
            return item
    return None


_QUEUE_EVENT_TYPE = {
    "running": "queue.dispatched",
    "awaiting_approval": "queue.approval_required",
    "blocked": "queue.blocked",
    "done": "queue.done",
    "failed": "queue.failed",
    "skipped": "queue.skipped",
    "cancelled": "queue.cancelled",
    "queued": "queue.enqueued",
}


def _apply_status(workspace: Path, item: dict[str, Any], fields: dict[str, Any]) -> None:
    """Validate + record a queue item's status change (mutates nothing but emits).

    Call right before applying ``fields`` to ``item``. A no-op or a non-status update is
    ignored; an illegal known→known transition is logged but still allowed (so we never
    wedge the queue), and every real change appends a durable ``queue.*`` event.
    """
    to = fields.get("status")
    frm = item["status"]  # every queue item always carries a status
    if to is None or to == frm:
        return
    if not transitions.is_valid("queue", frm, to):
        add_log_entry(
            "queue",
            f"invalid queue transition {frm}→{to} for {item.get('id')}",
            task_id=item.get("taskId"),
            step=item.get("step"),
            status="error",
        )
    state_store.append_event(
        workspace,
        _QUEUE_EVENT_TYPE.get(to, "queue.status_changed"),
        f"{item.get('label', item.get('step'))} → {to}" + (f": {fields.get('note')}" if fields.get("note") else ""),
        task_id=item.get("taskId"),
        step=item.get("step"),
        provider=item.get("provider"),
        data={"itemId": item.get("id"), "from": frm, "to": to},
    )


# ------------------------------------------------------------- the dispatcher


def _request_consult(data: dict, item: dict, record) -> None:
    """Ask the controller to review a finished step of a traffic-controlled task."""
    if any(c["taskId"] == item["taskId"] for c in data.get("consults", [])):
        return  # one pending consult per task is enough
    tail = ""
    if record is not None:
        tail = (record.stdout + ("\n" + record.stderr if record.stderr else ""))[-1500:]
    data.setdefault("consults", []).append(
        {
            "taskId": item["taskId"],
            "trigger": f"{item['label']} via {item['provider']} finished: {item['status']}"
            + (f" ({item['note']})" if item.get("note") else ""),
            "outputTail": tail,
            "requestedAt": now_iso(),
        }
    )


def _finalize_running(workspace: Path) -> None:
    """Sync pass: settle finished runs, block later steps of failed tasks, prune history."""
    data = load_queue(workspace)
    changed = False
    failed_tasks: set[str] = set()

    for item in data["items"]:
        if item["status"] != "running":
            continue
        record = RUNNER.runs.get(item.get("runId") or "")
        if record is None:
            fields: dict[str, Any] = {
                "status": "failed",
                "note": "run record lost (backend restarted)",
                "finishedAt": now_iso(),
            }
            _apply_status(workspace, item, fields)
            item.update(fields)
            failed_tasks.add(item["taskId"])
            changed = True
        elif record.status != "running":
            ok = record.status == "succeeded"
            fields = {
                "status": "done" if ok else ("cancelled" if record.status == "cancelled" else "failed"),
                "note": None if ok else f"{record.status} (exit {record.exit_code})",
                "finishedAt": now_iso(),
            }
            _apply_status(workspace, item, fields)
            item.update(fields)
            if not ok:
                failed_tasks.add(item["taskId"])
            changed = True
            # Closed loop: traffic-controlled tasks go back to the controller after every step.
            try:
                meta = task_service._load_meta(workspace, item["taskId"])
                if meta.get("orchestrated"):
                    _request_consult(data, item, record)
            except FileNotFoundError:
                pass

    if failed_tasks:
        for item in data["items"]:
            if item["status"] == "queued" and item["taskId"] in failed_tasks:
                fields = {"status": "blocked", "note": "an earlier step in this task did not succeed"}
                _apply_status(workspace, item, fields)
                item.update(fields)
                changed = True
        for tid in failed_tasks:
            try:
                task_service._add_event(
                    workspace,
                    tid,
                    "blocked",
                    "queue paused for this task — an earlier step did not succeed (approve items to continue)",
                )
            except FileNotFoundError:
                pass

    # prune terminal history
    terminal = [i for i in data["items"] if i["status"] not in ACTIVE_STATUSES]
    if len(terminal) > TERMINAL_KEEP:
        drop = {id(i) for i in terminal[: len(terminal) - TERMINAL_KEEP]}
        data["items"] = [i for i in data["items"] if id(i) not in drop]
        changed = True

    if changed:
        _save(workspace, data)


def _pick_candidate(workspace: Path, manual_mode: bool) -> Optional[str]:
    """First dispatchable item id: queue order, one per provider, intra-task order kept."""
    data = load_queue(workspace)
    busy = {r.provider for r in RUNNER.running_runs() if r.provider}
    waiting_tasks: set[str] = set()

    for item in data["items"]:
        status = item["status"]
        if status == "running":
            waiting_tasks.add(item["taskId"])
            continue
        if status in ("blocked", "awaiting_approval"):
            waiting_tasks.add(item["taskId"])
            continue
        if status != "queued":
            continue
        if item["taskId"] in waiting_tasks:
            continue
        provider = task_service.step_provider(workspace, item["step"])
        if provider in busy:
            waiting_tasks.add(item["taskId"])
            continue
        try:
            meta = task_service._load_meta(workspace, item["taskId"])
        except FileNotFoundError:
            fields = {"status": "failed", "note": "task no longer exists"}
            _apply_status(workspace, item, fields)
            item.update(fields)
            _save(workspace, data)
            return None
        if meta.get("fullSequence", {}).get("status") == "running":
            waiting_tasks.add(item["taskId"])
            continue
        if manual_mode:
            fields = {"status": "awaiting_approval", "note": "Manual Approval mode — approve to run"}
            _apply_status(workspace, item, fields)
            item.update(fields)
            _save(workspace, data)
            return None
        return item["id"]
    return None


async def dispatch_item(workspace: Path, item_id: str, confirm: bool = False, source: str = "auto") -> dict:
    """Run one queue item now (used by the dispatcher and the Approve button)."""
    data = load_queue(workspace)
    item = next((i for i in data["items"] if i["id"] == item_id), None)
    if item is None:
        return {"status": "not_found"}
    if item["status"] == "running":
        return {"status": "already_running"}

    result = await task_service.run_step(
        workspace,
        item["taskId"],
        item["step"],
        confirm=confirm,
        source=source,
        provider_override=item.get("providerOverride"),
    )

    if result["status"] == "started":
        _set_item(workspace, item_id, status="running", runId=result["runId"], note=None, startedAt=now_iso())
    elif result["status"] == "needs_confirmation":
        _set_item(workspace, item_id, status="blocked", note=result.get("warning", "needs confirmation"))
    elif result["status"] == "manual_preview":
        _set_item(workspace, item_id, status="awaiting_approval", note="Manual Approval mode — approve to run")
    elif result["status"] == "provider_missing":
        _set_item(workspace, item_id, status="skipped", note=result.get("message"), finishedAt=now_iso())
    else:
        _set_item(
            workspace, item_id, status="failed", note=result.get("message", result["status"]), finishedAt=now_iso()
        )
    return result


async def approve_item(workspace: Path, item_id: str) -> dict:
    """User-approved dispatch: overrides manual mode and red-Claude confirmation."""
    data = load_queue(workspace)
    item = next((i for i in data["items"] if i["id"] == item_id), None)
    if item is None:
        return {"status": "not_found"}
    provider = task_service.step_provider(workspace, item["step"])
    if provider in {r.provider for r in RUNNER.running_runs() if r.provider}:
        return {"status": "provider_busy", "message": f"`{provider}` is already running — try again when it finishes."}
    return await dispatch_item(workspace, item_id, confirm=True, source="manual")


def _unblock_task(workspace: Path, data: dict, task_id: str, *, exclude: Optional[str] = None) -> None:
    """Flip a task's blocked items back to queued so the pipeline can resume in order.
    Intra-task order is still enforced by the dispatcher, so this is safe."""
    for item in data["items"]:
        if item["taskId"] == task_id and item["status"] == "blocked" and item["id"] != exclude:
            fields = {"status": "queued", "note": None}
            _apply_status(workspace, item, fields)
            item.update(fields)


def _find_item(data: dict, item_id: str) -> Optional[dict]:
    return next((i for i in data["items"] if i["id"] == item_id), None)


def retry_item(workspace: Path, item_id: str) -> dict:
    """Re-enqueue a failed/blocked/skipped/cancelled item (incrementing its attempt)."""
    data = load_queue(workspace)
    item = _find_item(data, item_id)
    if item is None:
        return {"status": "not_found", **queue_state(workspace)}
    if item["status"] not in ("failed", "blocked", "skipped", "cancelled"):
        return {"status": "not_retryable", "message": f"cannot retry a {item['status']} item", **queue_state(workspace)}
    fields = {
        "status": "queued",
        "note": "retry requested",
        "attempt": int(item.get("attempt", 1)) + 1,
        "runId": None,
        "finishedAt": None,
    }
    _apply_status(workspace, item, fields)
    item.update(fields)
    _unblock_task(workspace, data, item["taskId"], exclude=item_id)
    _save(workspace, data)
    add_log_entry("queue", f"retry {item['label']} ({item['provider']})", task_id=item["taskId"], step=item["step"])
    return {"status": "ok", **queue_state(workspace)}


def skip_item(workspace: Path, item_id: str) -> dict:
    """Intentionally skip an item and let the task's later steps proceed."""
    data = load_queue(workspace)
    item = _find_item(data, item_id)
    if item is None:
        return {"status": "not_found", **queue_state(workspace)}
    if item["status"] == "running":
        return {"status": "running", "message": "cannot skip a running item", **queue_state(workspace)}
    fields = {"status": "skipped", "note": "skipped by user", "finishedAt": now_iso()}
    _apply_status(workspace, item, fields)
    item.update(fields)
    _unblock_task(workspace, data, item["taskId"], exclude=item_id)
    _save(workspace, data)
    add_log_entry("queue", f"skipped {item['label']} ({item['provider']})", task_id=item["taskId"], step=item["step"])
    return {"status": "ok", **queue_state(workspace)}


def reroute_item(workspace: Path, item_id: str, provider: str) -> dict:
    """Re-enqueue an item to run on a different provider than the routing default."""
    if provider not in provider_probe.AGENT_PROVIDER_IDS:
        return {"status": "bad_provider", "message": f"unknown provider `{provider}`", **queue_state(workspace)}
    data = load_queue(workspace)
    item = _find_item(data, item_id)
    if item is None:
        return {"status": "not_found", **queue_state(workspace)}
    if item["status"] == "running":
        return {"status": "running", "message": "cannot reroute a running item", **queue_state(workspace)}
    fields = {
        "status": "queued",
        "provider": provider,
        "providerOverride": provider,
        "note": f"rerouted to {provider}",
        "attempt": int(item.get("attempt", 1)) + 1,
        "runId": None,
        "finishedAt": None,
    }
    _apply_status(workspace, item, fields)
    item.update(fields)
    _unblock_task(workspace, data, item["taskId"], exclude=item_id)
    _save(workspace, data)
    add_log_entry("queue", f"rerouted {item['label']} → {provider}", task_id=item["taskId"], step=item["step"])
    return {"status": "ok", **queue_state(workspace)}


async def _process_consults(workspace: Path, manual: bool) -> None:
    """Run at most one pending controller consult, when the controller is free."""
    from . import chat_service  # local import: chat_service ↔ queue_service

    data = load_queue(workspace)
    consults = data.get("consults", [])
    if not consults:
        return
    if manual:
        dropped = consults
        data["consults"] = []
        _save(workspace, data)
        for c in dropped:
            try:
                task_service._add_event(
                    workspace,
                    c["taskId"],
                    "needs_user",
                    "controller consult skipped (Manual Approval mode) — queue the next step yourself",
                )
            except FileNotFoundError:
                pass
        return
    if chat_service.pending_state(workspace) is not None:
        return  # the user is mid-conversation with the controller — wait
    routing = config.get_workspace_routing(workspace)
    controller = routing.get("orchestrator", "claude")
    busy = {r.provider for r in RUNNER.running_runs() if r.provider}
    if controller in busy or any(r.step == "orchestrate" for r in RUNNER.running_runs()):
        return
    consult = consults.pop(0)
    _save(workspace, data)
    await chat_service.orchestrator_consult(
        workspace, consult["taskId"], consult["trigger"], consult.get("outputTail", "")
    )


async def tick(workspace: Path) -> None:
    _finalize_running(workspace)
    usage = usage_service.ensure_usage(workspace)
    manual = usage.get("orchestrationMode") == "manual_approval"
    await _process_consults(workspace, manual)
    candidate = _pick_candidate(workspace, manual)
    if candidate:
        await dispatch_item(workspace, candidate, confirm=False, source="auto")


async def dispatcher_loop() -> None:
    """Background loop: cues each queued step to its agent, one at a time per agent."""
    while True:
        try:
            workspace = config.get_current_workspace()
            if workspace is not None:
                await tick(workspace)
        except Exception as exc:  # noqa: BLE001 — the dispatcher must survive anything
            add_log_entry("queue", f"dispatcher error: {exc}", status="error")
        await asyncio.sleep(TICK_SECONDS)
