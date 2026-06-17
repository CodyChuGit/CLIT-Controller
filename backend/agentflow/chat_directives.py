"""Parsing for controller decisions (I/O rebuild + Pillar 5).

Controller output is read in priority order, newest-protocol first:

1. **CLITC_RESULT_V1 (authoritative)** — the deterministic, sentinel-framed result
   parsed + validated by :mod:`agentflow.controller_protocol`. When a v1 block is
   present, ONLY it is honored: a valid block drives the action, and an **invalid**
   v1 block yields no action (so no state mutates) and is NEVER silently downgraded
   to the legacy parsers. This is the primary controller protocol.
2. **Legacy ``agentflow`` JSON decisions** — a fenced ``agentflow`` block of
   contract-validated decisions (bounded migration fallback).
3. **Legacy ``agentflow-*`` markdown blocks** — ``-task``/``-queue``/``-run``/
   ``-done``/``-needs-user`` (bounded migration fallback).

Every ``parse_*`` reader applies this order. All existing consumers
(``chat_service``) therefore use the deterministic protocol with no change, while
the legacy forms remain available during migration. See
docs/input-output-rebuild/02-protocols.md.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from . import contracts
from . import controller_protocol as cp
from .workflow import FULL_SEQUENCE, STEP_DEFS

TASK_DIRECTIVE_RE = re.compile(r"```agentflow-task\s*\n(.*?)```", re.DOTALL)
QUEUE_DIRECTIVE_RE = re.compile(r"```agentflow-queue\s*\n(.*?)```", re.DOTALL)
DONE_DIRECTIVE_RE = re.compile(r"```agentflow-done\s*\n(.*?)```", re.DOTALL)
NEEDS_USER_DIRECTIVE_RE = re.compile(r"```agentflow-needs-user\s*\n(.*?)```", re.DOTALL)
RUN_DIRECTIVE_RE = re.compile(r"```agentflow-run\s*\n(.*?)```", re.DOTALL)
# Native structured output: a fenced ``agentflow`` block of JSON (not ``agentflow-*``).
STRUCTURED_RE = re.compile(r"```agentflow\s*\n(.*?)```", re.DOTALL)

MAX_RUN_DIRECTIVES = 3


def _v1(text: str):
    """The CLITC_RESULT_V1 parse for ``text``: (result, failure, meta)."""
    return cp.parse_controller_result(text)


def controller_failure(text: str) -> Optional[contracts.FailureRecord]:
    """A typed failure when a CLITC_RESULT_V1 block is present but invalid, else
    None. Callers surface this instead of acting (the protocol mutates no state on
    invalid output, and is never downgraded to the legacy parsers)."""
    _result, failure, _meta = _v1(text)
    return failure


def _v1_blocks_present(text: str) -> bool:
    return _v1(text)[2].source == "v1"


def extract_structured_decisions(text: str) -> list[dict]:
    """Validated controller decisions from any ``agentflow`` JSON blocks in ``text``.

    Accepts an envelope ``{"decisions": [...]}``, a bare list, or a single object.
    Each item is validated via :func:`contracts.validate`; invalid/unknown decisions
    are skipped (fail-safe). Returns the list of validated decision dicts (kind-tagged).
    """
    out: list[dict] = []
    for match in STRUCTURED_RE.finditer(text or ""):
        try:
            data = json.loads(match.group(1).strip())
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get("decisions"), list):
            items = data["decisions"]
        elif isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = [data]
        else:
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            model, _failure = contracts.validate(str(item.get("kind", "")), item)
            if model is not None:
                out.append(model.model_dump())
    return out


def _normalize_steps(steps) -> Optional[list[str]]:
    """Coerce a structured ``queueSteps`` value to valid step ids (or None)."""
    if not isinstance(steps, list) or not steps:
        return None
    if any(s == "full" for s in steps):
        return list(FULL_SEQUENCE)
    valid = [s for s in steps if s in STEP_DEFS]
    return valid or None


def parse_run_directives(text: str) -> list[str]:
    result, _failure, meta = _v1(text)
    if meta.source == "v1":
        if result and result.action.type == "run_command":
            return [result.action.command.strip()][:MAX_RUN_DIRECTIVES]
        return []  # v1 present but not a run (or invalid) — no legacy fallback
    structured = extract_structured_decisions(text)
    if structured:
        cmds = [str(d["command"]).strip() for d in structured if d["kind"] == "run" and d.get("command")]
        return cmds[:MAX_RUN_DIRECTIVES]
    commands: list[str] = []
    for match in RUN_DIRECTIVE_RE.finditer(text or ""):
        for line in match.group(1).splitlines():
            if line.lower().startswith("command:"):
                cmd = line[8:].strip()
                if cmd:
                    commands.append(cmd)
    return commands[:MAX_RUN_DIRECTIVES]


def _parse_reason_block(regex: re.Pattern[str], text: str) -> Optional[str]:
    match = regex.search(text or "")
    if not match:
        return None
    for line in match.group(1).splitlines():
        if line.lower().startswith("reason:"):
            return line[7:].strip() or "no reason given"
    return "no reason given"


def _structured_reason(structured: list[dict], kind: str) -> Optional[str]:
    for d in structured:
        if d["kind"] == kind:
            return str(d.get("reason") or "no reason given")
    return None


def parse_done_directive(text: str) -> Optional[str]:
    result, _failure, meta = _v1(text)
    if meta.source == "v1":
        if result and result.action.type == "complete_task":
            return result.action.reason or "no reason given"
        return None
    structured = extract_structured_decisions(text)
    if structured:
        return _structured_reason(structured, "done")
    return _parse_reason_block(DONE_DIRECTIVE_RE, text)


def parse_needs_user_directive(text: str) -> Optional[str]:
    result, _failure, meta = _v1(text)
    if meta.source == "v1":
        if result and result.action.type == "request_user":
            return result.action.reason or "no reason given"
        return None
    structured = extract_structured_decisions(text)
    if structured:
        return _structured_reason(structured, "needs_user")
    return _parse_reason_block(NEEDS_USER_DIRECTIVE_RE, text)


def _parse_steps(raw: str) -> Optional[list[str]]:
    raw = raw.strip().lower()
    if not raw:
        return None
    if raw == "full":
        return list(FULL_SEQUENCE)
    steps = [step.strip() for step in raw.split(",") if step.strip()]
    if steps and all(step in STEP_DEFS for step in steps):
        return steps
    return None


def parse_task_directive(text: str) -> Optional[tuple[str, str, Optional[list[str]]]]:
    result, _failure, meta = _v1(text)
    if meta.source == "v1":
        if result and result.action.type == "create_task":
            return result.action.title[:200], result.action.goal, _normalize_steps(result.action.steps)
        return None
    structured = extract_structured_decisions(text)
    if structured:
        for d in structured:
            if d["kind"] == "task" and d.get("title") and d.get("goal"):
                return str(d["title"])[:200], str(d["goal"]), _normalize_steps(d.get("queueSteps"))
        return None
    match = TASK_DIRECTIVE_RE.search(text or "")
    if not match:
        return None
    title, goal_lines, queue_steps, in_goal = None, [], None, False
    for line in match.group(1).splitlines():
        lower = line.lower()
        if lower.startswith("title:") and title is None:
            title = line[6:].strip()
            in_goal = False
        elif lower.startswith("goal:"):
            goal_lines.append(line[5:].strip())
            in_goal = True
        elif lower.startswith("queue:"):
            queue_steps = _parse_steps(line[6:])
            in_goal = False
        elif in_goal and line.strip():
            goal_lines.append(line.strip())
    goal = " ".join(goal_lines).strip()
    if not title or not goal:
        return None
    return title[:200], goal, queue_steps


def parse_queue_directive(text: str) -> Optional[tuple[str, list[str]]]:
    result, _failure, meta = _v1(text)
    if meta.source == "v1":
        if result and result.action.type == "queue_steps":
            steps = _normalize_steps(result.action.steps)
            if steps:
                return result.action.taskId, steps
        return None
    structured = extract_structured_decisions(text)
    if structured:
        for d in structured:
            if d["kind"] == "queue":
                steps = _normalize_steps(d.get("steps"))
                if d.get("taskRef") and steps:
                    return str(d["taskRef"]), steps
        return None
    match = QUEUE_DIRECTIVE_RE.search(text or "")
    if not match:
        return None
    task_ref, steps = None, None
    for line in match.group(1).splitlines():
        lower = line.lower()
        if lower.startswith("task:"):
            task_ref = line[5:].strip()
        elif lower.startswith("steps:"):
            steps = _parse_steps(line[6:])
    if not task_ref or not steps:
        return None
    return task_ref, steps


def controller_directive_records(text: str) -> list[dict]:
    """Deterministic, validated records for the controller directives in ``text``
    (Pillar 5). Bridges the legacy markdown-block parsers to the versioned
    contracts so controller decisions can be emitted and styled as typed records
    rather than re-parsed from prose. Additive — does not change parsing behaviour.
    """
    records: list[contracts.ControllerDirective] = []
    task = parse_task_directive(text)
    if task:
        title, goal, steps = task
        records.append(contracts.TaskDirective(title=title, goal=goal, queueSteps=steps))
    queue = parse_queue_directive(text)
    if queue:
        task_ref, steps = queue
        records.append(contracts.QueueDirective(taskRef=task_ref, steps=steps))
    for cmd in parse_run_directives(text):
        records.append(contracts.RunDirective(command=cmd))
    done = parse_done_directive(text)
    if done:
        records.append(contracts.DoneDirective(reason=done))
    needs_user = parse_needs_user_directive(text)
    if needs_user:
        records.append(contracts.NeedsUserDirective(reason=needs_user))
    return [r.model_dump() for r in records]


def strip_action_blocks(text: str) -> str:
    # Remove the authoritative CLITC_RESULT_V1 block first so its JSON never renders
    # as prose, then the legacy directive blocks.
    out = cp.strip_result_block(text or "")
    for regex in (
        STRUCTURED_RE,
        TASK_DIRECTIVE_RE,
        QUEUE_DIRECTIVE_RE,
        RUN_DIRECTIVE_RE,
        DONE_DIRECTIVE_RE,
        NEEDS_USER_DIRECTIVE_RE,
    ):
        out = regex.sub("", out)
    return out.strip()
