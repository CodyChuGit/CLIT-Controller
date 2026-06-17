"""Parsing for controller fenced directive blocks."""

from __future__ import annotations

import re
from typing import Optional

from . import contracts
from .workflow import FULL_SEQUENCE, STEP_DEFS

TASK_DIRECTIVE_RE = re.compile(r"```agentflow-task\s*\n(.*?)```", re.DOTALL)
QUEUE_DIRECTIVE_RE = re.compile(r"```agentflow-queue\s*\n(.*?)```", re.DOTALL)
DONE_DIRECTIVE_RE = re.compile(r"```agentflow-done\s*\n(.*?)```", re.DOTALL)
NEEDS_USER_DIRECTIVE_RE = re.compile(r"```agentflow-needs-user\s*\n(.*?)```", re.DOTALL)
RUN_DIRECTIVE_RE = re.compile(r"```agentflow-run\s*\n(.*?)```", re.DOTALL)

MAX_RUN_DIRECTIVES = 3


def parse_run_directives(text: str) -> list[str]:
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


def parse_done_directive(text: str) -> Optional[str]:
    return _parse_reason_block(DONE_DIRECTIVE_RE, text)


def parse_needs_user_directive(text: str) -> Optional[str]:
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
    out = text or ""
    for regex in (
        TASK_DIRECTIVE_RE,
        QUEUE_DIRECTIVE_RE,
        RUN_DIRECTIVE_RE,
        DONE_DIRECTIVE_RE,
        NEEDS_USER_DIRECTIVE_RE,
    ):
        out = regex.sub("", out)
    return out.strip()
