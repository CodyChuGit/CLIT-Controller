"""Durable machine state beside the markdown artifacts.

The beta keeps task/queue state in human-readable JSON, but run records live only in
memory (``ProcessRunner.runs``) and vanish on restart — which is how a queue item can
be stuck ``running`` forever. This module adds three durable, schema-versioned ledgers
under ``<workspace>/.agentflow/``:

- ``events.json``  — append-only timeline of every task/queue/run/approval transition.
- ``runs.json``    — the run ledger: enough to recover and inspect a run after restart.
- ``approvals.json`` — pending/resolved approvals for risky actions.

Markdown handoff files and ``task.json`` stay authoritative for human reading; these
ledgers are authoritative for *recovery*. Writes go through ``config.write_json`` which
is atomic (tmp file + rename).
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from . import config, event_bus, paths
from .process_runner import now_iso
from .redaction import redact, redact_data

SCHEMA_VERSION = 1
MAX_EVENTS = 2000  # bounded timeline; oldest pruned
MAX_RUNS = 200  # bounded run ledger; never prunes a `running` run

# Run failure kinds (docs/orchestrator-backend/02 §Run). A run that is not `running`
# and has no failure kind is a clean success.
FAILURE_KINDS = {
    "provider_missing",
    "auth_required",
    "policy_denied",
    "validation_error",
    "start_error",
    "timeout",
    "exit_nonzero",
    "cancelled",
    "backend_restart",
    "unknown",
}


# ------------------------------------------------------------------ file paths


def events_file(workspace: Path) -> Path:
    return paths.workspace_app_dir(workspace) / "events.json"


def runs_file(workspace: Path) -> Path:
    return paths.workspace_app_dir(workspace) / "runs.json"


def approvals_file(workspace: Path) -> Path:
    return paths.workspace_app_dir(workspace) / "approvals.json"


def _load_doc(path: Path, key: str, empty):
    """Load a schema-versioned ledger, migrating/repairing a missing or stale shape."""
    data = config.read_json(path, None)
    if not isinstance(data, dict) or key not in data:
        return {"schemaVersion": SCHEMA_VERSION, "cursor": 0, key: empty}
    data.setdefault("schemaVersion", SCHEMA_VERSION)
    data.setdefault("cursor", 0)
    # Forward migration hook: future versions reshape here before use.
    return data


# ---------------------------------------------------------------------- events


def append_event(
    workspace: Path,
    type_: str,
    detail: str = "",
    *,
    task_id: Optional[str] = None,
    step: Optional[str] = None,
    provider: Optional[str] = None,
    data: Optional[dict] = None,
) -> dict:
    """Append one durable timeline event and return it (with a monotonic id/cursor)."""
    doc = _load_doc(events_file(workspace), "events", [])
    doc["cursor"] = int(doc.get("cursor", 0)) + 1
    # Redact before persisting: the durable timeline must not store secrets, and a
    # command/action carried in `data` could embed one (audit P1-02). The mirrored
    # event-bus publish below redacts its own copy independently.
    event = {
        "id": doc["cursor"],
        "time": now_iso(),
        "type": type_,
        "taskId": task_id,
        "step": step,
        "provider": provider,
        "detail": redact(detail) if detail else detail,
        "data": redact_data(data) if data else {},
    }
    events = doc["events"]
    events.append(event)
    if len(events) > MAX_EVENTS:
        del events[: len(events) - MAX_EVENTS]
    config.write_json(events_file(workspace), doc)
    # Mirror to the live event bus so every structural transition streams to the
    # Agent Dock / Tasks / Logs / footer over SSE (and the polling fallback).
    d = data or {}
    event_bus.BUS.publish(
        workspace,
        type_,
        detail=detail,
        provider=provider,
        task_id=task_id,
        step=step,
        run_id=d.get("runId"),
        queue_item_id=d.get("itemId") or d.get("queueItemId"),
        data=d,
    )
    return event


def read_events(workspace: Path, after: int = 0, limit: Optional[int] = None) -> list[dict]:
    """Events with id > ``after`` (the polling cursor), oldest first."""
    doc = _load_doc(events_file(workspace), "events", [])
    out = [e for e in doc["events"] if e.get("id", 0) > after]
    if limit is not None:
        out = out[-limit:]
    return out


def events_cursor(workspace: Path) -> int:
    return int(_load_doc(events_file(workspace), "events", []).get("cursor", 0))


# ------------------------------------------------------------------- run ledger


def persist_run(workspace: Path, record: dict) -> None:
    """Upsert one run record into the durable ledger (keyed by run id)."""
    rid = record.get("id")
    if not rid:
        return
    doc = _load_doc(runs_file(workspace), "runs", {})
    runs = doc["runs"]
    runs[rid] = record
    # Bound the ledger but never drop a run still marked running.
    if len(runs) > MAX_RUNS:
        finished = [r for r in runs.values() if r.get("status") != "running"]
        finished.sort(key=lambda r: r.get("startedAt") or "")
        for stale in finished[: len(runs) - MAX_RUNS]:
            runs.pop(stale["id"], None)
    config.write_json(runs_file(workspace), doc)


def load_runs(workspace: Path) -> dict[str, dict]:
    return _load_doc(runs_file(workspace), "runs", {})["runs"]


def get_run(workspace: Path, run_id: str) -> Optional[dict]:
    return load_runs(workspace).get(run_id)


def runs_for_task(workspace: Path, task_id: str) -> list[dict]:
    runs = [r for r in load_runs(workspace).values() if r.get("taskId") == task_id]
    return sorted(runs, key=lambda r: r.get("startedAt") or "")


# -------------------------------------------------------------------- approvals


def create_approval(
    workspace: Path,
    *,
    action: str,
    kind: str = "command",
    source: str = "orchestrator",
    provider: Optional[str] = None,
    task_id: Optional[str] = None,
    reason: str = "",
) -> dict:
    """Record a pending approval for a risky action and return it."""
    doc = _load_doc(approvals_file(workspace), "approvals", {})
    approval = {
        "id": uuid.uuid4().hex[:8],
        "action": action,
        "kind": kind,
        "source": source,
        "provider": provider,
        "taskId": task_id,
        "reason": reason,
        "status": "pending",
        "createdAt": now_iso(),
        "resolvedAt": None,
        "resolver": None,
    }
    doc["approvals"][approval["id"]] = approval
    config.write_json(approvals_file(workspace), doc)
    append_event(
        workspace,
        "approval.required",
        reason or action,
        task_id=task_id,
        provider=provider,
        data={"approvalId": approval["id"], "action": action},
    )
    return approval


def get_approval(workspace: Path, approval_id: str) -> Optional[dict]:
    return _load_doc(approvals_file(workspace), "approvals", {})["approvals"].get(approval_id)


def resolve_approval(workspace: Path, approval_id: str, *, approved: bool, resolver: str = "user") -> Optional[dict]:
    doc = _load_doc(approvals_file(workspace), "approvals", {})
    approval = doc["approvals"].get(approval_id)
    if approval is None or approval["status"] != "pending":
        return approval
    approval["status"] = "approved" if approved else "rejected"
    approval["resolvedAt"] = now_iso()
    approval["resolver"] = resolver
    config.write_json(approvals_file(workspace), doc)
    append_event(
        workspace,
        "approval.granted" if approved else "approval.rejected",
        approval.get("reason") or approval.get("action", ""),
        task_id=approval.get("taskId"),
        provider=approval.get("provider"),
        data={"approvalId": approval_id},
    )
    return approval


def list_approvals(workspace: Path, *, pending_only: bool = False) -> list[dict]:
    approvals = list(_load_doc(approvals_file(workspace), "approvals", {})["approvals"].values())
    if pending_only:
        approvals = [a for a in approvals if a["status"] == "pending"]
    approvals = sorted(approvals, key=lambda a: a["createdAt"])
    # Redact for display only; the on-disk record keeps the raw action so an
    # approved command can still be replayed verbatim on approve (audit P1-02).
    return [{**a, "action": redact(a.get("action", "")), "reason": redact(a.get("reason", ""))} for a in approvals]


# --------------------------------------------------------------------- recovery


def _pid_alive(pid: Optional[int]) -> bool:
    """Best-effort liveness check. PIDs can be reused, so this only refines wording —
    recovery still settles the run because we can no longer manage or capture it."""
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OverflowError, ValueError):
        return True
    return True


def recover_workspace(workspace: Path) -> dict:
    """Reconcile durable state after a restart so nothing is left ``running`` forever.

    A run can only be driven by the interpreter that spawned it; once the backend
    restarts, ``ProcessRunner`` no longer owns any previously-running process. So every
    persisted ``running`` run is settled as ``backend_restart`` (the truthful terminal
    state), its queue item is failed-as-interrupted, its task step is unstuck, and later
    queued items for an interrupted task are blocked. Returns a small summary; callers
    decide whether to log it. Idempotent: a clean workspace recovers to all-zeros.
    """
    if not paths.workspace_app_dir(workspace).is_dir():
        return {"runs": 0, "items": 0, "steps": 0}

    # Avoid import cycles: recovery touches queue + task services.
    from . import queue_service, task_service
    from .process_runner import RUNNER

    summary = {"runs": 0, "items": 0, "steps": 0}
    interrupted_runs: dict[str, str] = {}  # runId -> note

    # 1) Settle stale runs in the durable ledger.
    doc = _load_doc(runs_file(workspace), "runs", {})
    changed = False
    for rid, rec in doc["runs"].items():
        if rec.get("status") != "running":
            continue
        if rid in RUNNER.procs:
            continue  # genuinely still managed (same process) — leave it
        note = (
            "process still detached after restart — output no longer captured"
            if _pid_alive(rec.get("pid"))
            else "process ended while the backend was down"
        )
        rec.update(status="failed", failureKind="backend_restart", endedAt=now_iso(), recoveryNote=note)
        interrupted_runs[rid] = note
        summary["runs"] += 1
        changed = True
        append_event(
            workspace,
            "run.finished",
            f"recovered after restart: {note}",
            task_id=rec.get("taskId"),
            step=rec.get("step"),
            provider=rec.get("provider"),
            data={"runId": rid, "status": "failed", "failureKind": "backend_restart"},
        )
    if changed:
        config.write_json(runs_file(workspace), doc)

    # 2) Settle queue items that were running, and block later steps of their tasks.
    qdata = queue_service.load_queue(workspace)
    failed_tasks: set[str] = set()
    qchanged = False
    for item in qdata["items"]:
        if item.get("status") != "running":
            continue
        note = interrupted_runs.get(item.get("runId") or "", "backend restarted before this step finished")
        item.update(status="failed", note=note, finishedAt=now_iso())
        failed_tasks.add(item["taskId"])
        summary["items"] += 1
        qchanged = True
        append_event(
            workspace,
            "queue.failed",
            note,
            task_id=item["taskId"],
            step=item.get("step"),
            provider=item.get("provider"),
            data={"itemId": item["id"], "reason": "backend_restart"},
        )
    if failed_tasks:
        for item in qdata["items"]:
            if item.get("status") == "queued" and item["taskId"] in failed_tasks:
                item.update(status="blocked", note="an earlier step in this task was interrupted by a restart")
                qchanged = True
    if qchanged:
        queue_service._save(workspace, qdata)

    # 3) Unstick task steps that claim to be running with no live run.
    for meta in task_service.list_tasks(workspace):
        tid = meta["id"]
        meta_changed = False
        for step, s in meta.get("steps", {}).items():
            if s.get("status") == "running" and s.get("runId", None) not in RUNNER.procs:
                s.update(status="failed", recoveryNote="interrupted by backend restart", updatedAt=now_iso())
                summary["steps"] += 1
                meta_changed = True
                append_event(
                    workspace,
                    "task.status_changed",
                    "step interrupted by backend restart",
                    task_id=tid,
                    step=step,
                    provider=s.get("provider"),
                    data={"status": "failed", "reason": "backend_restart"},
                )
        seq = meta.get("fullSequence") or {}
        if seq.get("status") == "running":
            meta["fullSequence"] = {"status": "interrupted", "currentStep": seq.get("currentStep")}
            meta_changed = True
        if meta_changed:
            statuses = [s.get("status") for s in meta["steps"].values()]
            meta["status"] = "idle" if set(statuses) == {"idle"} else "in_progress"
            task_service._save_meta(workspace, meta)

    if summary["runs"] or summary["items"] or summary["steps"]:
        append_event(
            workspace,
            "recovery.completed",
            f"restart recovery: {summary['runs']} run(s), {summary['items']} queue item(s), "
            f"{summary['steps']} step(s) settled",
            data=summary,
        )
    return summary
