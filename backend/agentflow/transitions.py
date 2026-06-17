"""Explicit state machines for tasks, steps, queue items, and runs.

These tables make invalid transitions detectable instead of letting status strings be
overwritten anywhere. The goal of this slice is not to rewrite every existing mutation,
but to give the durable/recovery/queue paths a single validated chokepoint and to make
the legal state space testable. ``is_valid`` is permissive about unknown statuses (it
only rejects a known→known transition that isn't allowed) so the helpers can be adopted
incrementally without breaking legacy values still in older ``task.json`` files.
"""

from __future__ import annotations

# ----------------------------------------------------------------- status sets

TASK_STATUSES = {"new", "idle", "in_progress", "running", "needs_user", "done", "failed", "cancelled", "abandoned"}

STEP_STATUSES = {
    "idle",
    "queued",
    "awaiting_approval",
    "running",
    "succeeded",
    "skipped",
    "skipped_budget",
    "blocked",
    "failed",
    "cancelled",
    "provider_missing",
    "policy_denied",
    "error",
}

QUEUE_STATUSES = {
    "queued",
    "awaiting_approval",
    "blocked",
    "running",
    "done",
    "failed",
    "skipped",
    "cancelled",
}

RUN_STATUSES = {"running", "succeeded", "failed", "cancelled", "error"}

# Terminal states never transition further on their own.
QUEUE_TERMINAL = {"done", "failed", "skipped", "cancelled"}
STEP_TERMINAL = {
    "succeeded",
    "skipped",
    "skipped_budget",
    "failed",
    "cancelled",
    "provider_missing",
    "policy_denied",
    "error",
}


# --------------------------------------------------------- allowed transitions
# Each map: from_status -> set(to_status). Re-stating the same status is always fine.

QUEUE_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "awaiting_approval", "blocked", "skipped", "cancelled", "failed"},
    "awaiting_approval": {"queued", "running", "skipped", "cancelled", "blocked"},
    "blocked": {"queued", "running", "skipped", "cancelled", "failed"},
    "running": {"done", "failed", "cancelled"},
    # Terminal states can be revived intentionally (retry / skip / reroute).
    "failed": {"queued", "skipped", "cancelled"},
    "cancelled": {"queued", "skipped"},
    "skipped": {"queued"},
    "done": set(),
}

STEP_TRANSITIONS: dict[str, set[str]] = {
    "idle": {
        "queued",
        "awaiting_approval",
        "running",
        "provider_missing",
        "policy_denied",
        "skipped",
        "skipped_budget",
        "blocked",
    },
    "queued": {"running", "awaiting_approval", "blocked", "provider_missing", "policy_denied", "skipped", "cancelled"},
    "awaiting_approval": {"queued", "running", "skipped", "cancelled"},
    "blocked": {"queued", "running", "skipped", "cancelled"},
    "running": {"succeeded", "failed", "cancelled", "error"},
    # Terminal step states can be retried back into the pipeline.
    "succeeded": {"queued", "running", "idle"},
    "failed": {"queued", "running", "skipped", "idle"},
    "error": {"queued", "running", "skipped", "idle"},
    "cancelled": {"queued", "running", "idle"},
    "provider_missing": {"queued", "running", "skipped", "idle"},
    "policy_denied": {"queued", "running", "skipped", "idle"},
    "skipped": {"queued", "running", "idle"},
    "skipped_budget": {"queued", "running", "idle"},
}

TASK_TRANSITIONS: dict[str, set[str]] = {
    "new": {"idle", "in_progress", "running", "cancelled", "abandoned"},
    "idle": {"in_progress", "running", "cancelled", "abandoned"},
    "in_progress": {"running", "idle", "done", "needs_user", "failed", "cancelled", "abandoned"},
    "running": {"in_progress", "idle", "done", "needs_user", "failed", "cancelled"},
    "needs_user": {"in_progress", "running", "cancelled", "abandoned"},
    "failed": {"in_progress", "running", "idle", "cancelled", "abandoned"},
    "done": {"in_progress"},  # reopen for follow-up work
    "cancelled": {"in_progress"},
    "abandoned": set(),
}

RUN_TRANSITIONS: dict[str, set[str]] = {
    "running": {"succeeded", "failed", "cancelled", "error"},
}

_TABLES = {
    "task": (TASK_TRANSITIONS, TASK_STATUSES),
    "step": (STEP_TRANSITIONS, STEP_STATUSES),
    "queue": (QUEUE_TRANSITIONS, QUEUE_STATUSES),
    "run": (RUN_TRANSITIONS, RUN_STATUSES),
}


def is_valid(kind: str, frm: str, to: str) -> bool:
    """True if ``frm -> to`` is allowed for ``kind`` (task|step|queue|run).

    Permissive by design: a no-op (frm == to) is allowed, and any transition that
    involves a status not in the known set is allowed so legacy/unknown values don't
    block adoption. Only a *known→known* transition outside the table is rejected.
    """
    table, known = _TABLES[kind]
    if frm == to:
        return True
    if frm not in known or to not in known:
        return True
    return to in table.get(frm, set())
