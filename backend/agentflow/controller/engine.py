"""Controller turn engine: parse a finished controller CLI's output and act.

Priority order (never inverted):

1. A valid CLITC_RESULT_V1 block — the primary protocol — drives exactly one
   validated action through ``actions.execute``.
2. A present-but-invalid block is a typed failure: a ``controller.result_invalid``
   event is emitted, the user is told, and NO state mutates (no legacy downgrade).
3. No block at all falls back to the bounded legacy ``agentflow-*`` directives,
   with a ``controller.legacy_directives`` compatibility warning event.

Every turn ends with a durable ``controller.turn_completed`` event carrying the
typed turn record (source, provider, taskId, runId, resultSource, actionType,
status) — the state-machine ledger from the revamp brief.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .. import chat_directives, controller_protocol, state_store
from ..controller_protocol import (
    CompleteTaskAction,
    ControllerAction,
    CreateTaskAction,
    QueueStepsAction,
    RequestUserAction,
    RunCommandAction,
)
from . import actions


def _legacy_actions(out: str) -> list[ControllerAction]:
    """Legacy agentflow-* / fenced-JSON directives mapped onto the closed action
    union, so the fallback runs through the same executor as the v1 protocol.
    Only reachable when no CLITC_RESULT_V1 block exists (parsers are v1-first)."""
    acts: list[ControllerAction] = []
    task = chat_directives.parse_task_directive(out)
    if task is not None:
        title, goal, steps = task
        acts.append(CreateTaskAction(title=title, goal=goal, steps=steps or []))
    queued = chat_directives.parse_queue_directive(out)
    if queued is not None:
        ref, steps = queued
        acts.append(QueueStepsAction(taskId=ref, steps=steps))
    for cmd in chat_directives.parse_run_directives(out):
        acts.append(RunCommandAction(command=cmd))
    done = chat_directives.parse_done_directive(out)
    if done is not None:
        acts.append(CompleteTaskAction(reason=done))
    needs_user = chat_directives.parse_needs_user_directive(out)
    if needs_user is not None:
        acts.append(RequestUserAction(reason=needs_user))
    return acts


async def apply_controller_output(
    workspace: Path,
    out: str,
    *,
    provider: str,
    source: str,
    run_id: Optional[str] = None,
    task_id: Optional[str] = None,
) -> dict:
    """Parse ``out`` and execute the controller's decision. Returns the turn record:
    {"resultSource", "status", "actionType"} where status is one of
    actioned | failed | invalid | no_action."""
    result, failure, meta = controller_protocol.parse_controller_result(out)
    base = {"source": source, "provider": provider, "taskId": task_id, "runId": run_id}

    if failure is not None:
        # Typed no-action path: surface the failure, mutate nothing, never downgrade.
        state_store.append_event(
            workspace,
            "controller.result_invalid",
            f"{failure.title}: {failure.summary}",
            task_id=task_id,
            provider=provider,
            data={**base, "blocks": meta.blocks},
        )
        actions._message(workspace, provider, f"{failure.title} — no action was taken.")
        if task_id:
            actions._task_event(
                workspace,
                task_id,
                "needs_user",
                f"controller returned an invalid result — {failure.summary}",
                provider=provider,
            )
        turn = {"resultSource": "clitc_result_v1", "status": "invalid", "actionType": None}
    elif result is not None:
        if meta.blocks > 1:
            # Model misbehaviour signal: the last valid block won, but say so durably.
            state_store.append_event(
                workspace,
                "controller.result_misbehaviour",
                f"{meta.blocks} CLITC_RESULT_V1 blocks in one reply — used the last valid one",
                task_id=task_id,
                provider=provider,
                data=base,
            )
        outcome = await actions.execute(
            workspace, result.action, provider=provider, source=source, task_id=task_id, run_id=run_id
        )
        if task_id and source == "consult" and result.action.type not in ("request_user", "complete_task"):
            actions._task_event(
                workspace,
                task_id,
                "consult",
                f"controller decision: {result.action.type} — {outcome['note']}"[:300],
                provider=provider,
            )
        turn = {
            "resultSource": "clitc_result_v1",
            "status": "actioned" if outcome["ok"] else "failed",
            "actionType": result.action.type,
        }
    else:
        legacy = _legacy_actions(out)
        if legacy:
            state_store.append_event(
                workspace,
                "controller.legacy_directives",
                f"legacy agentflow directives honored ({', '.join(a.type for a in legacy)}) — "
                "the controller should emit CLITC_RESULT_V1",
                task_id=task_id,
                provider=provider,
                data=base,
            )
            ok = True
            for act in legacy:
                outcome = await actions.execute(
                    workspace, act, provider=provider, source=source, task_id=task_id, run_id=run_id
                )
                ok = ok and outcome["ok"]
            turn = {
                "resultSource": "legacy",
                "status": "actioned" if ok else "failed",
                "actionType": legacy[0].type,
            }
        else:
            turn = {"resultSource": "none", "status": "no_action", "actionType": None}

    state_store.append_event(
        workspace,
        "controller.turn_completed",
        f"{source} turn via {provider}: {turn['status']}"
        + (f" ({turn['actionType']})" if turn["actionType"] else ""),
        task_id=task_id,
        provider=provider,
        step="orchestrate" if source == "consult" else "chat",
        data={**base, **turn},
    )
    return turn
