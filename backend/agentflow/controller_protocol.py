"""Deterministic controller protocol — CLITC_RESULT_V1 (I/O rebuild, Plane 3).

Separates the controller's live human-readable NARRATIVE (prose, streamed normally)
from exactly ONE authoritative, validated control RESULT. The controller (an
installed CLI, not a structured-output API) streams prose, then emits a single
sentinel-framed JSON block:

    ...human-readable reasoning streams here...

    <<<CLITC_RESULT_V1
    {"schemaVersion":"1","kind":"controller_result",
     "message":{"summary":"Ready to implement.","details":["spec exists"]},
     "action":{"type":"queue_steps","taskId":"task-123","steps":["claude_implement"]}}
    CLITC_RESULT_V1>>>

Parsing rules (mission Phase 2):
- Prose-tolerant: surrounding narrative is ignored.
- Exactly one authoritative result; if multiple blocks appear, the LAST valid one
  wins and the count is reported in metadata (a model misbehaviour signal).
- Bounded payload size (``MAX_RESULT_BYTES``).
- Full validation before the result is actionable. Invalid output yields a typed
  ``FailureRecord`` and NO result — callers must not mutate state from it.
- No business field is regex-parsed; the JSON is parsed once and validated against
  a closed, versioned schema. ``run_command``/``request_approval`` carry a command
  STRING that the existing policy classifier + argv runner vet at execution time —
  this module never executes anything or touches a shell.
- Unknown ``schemaVersion`` fails safely (forward-compatible rejection).

The legacy ``agentflow-*`` markdown / ``agentflow`` JSON directives remain only as a
bounded, explicitly-marked migration fallback, handled by the caller — not here.
"""

from __future__ import annotations

import json
import re
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, ValidationError

from .contracts import FailureRecord

PROTOCOL_VERSION = "1"
OPEN = "<<<CLITC_RESULT_V1"
CLOSE = "CLITC_RESULT_V1>>>"
MAX_RESULT_BYTES = 16_384

# Capture ANY content between the sentinels; JSON/schema validation rejects bad
# bodies (so malformed content fails loudly rather than being silently ignored).
_BLOCK_RE = re.compile(re.escape(OPEN) + r"\s*(.*?)\s*" + re.escape(CLOSE), re.DOTALL)


# --------------------------------------------------------------- closed action union


class AnswerAction(BaseModel):
    type: Literal["answer"] = "answer"


class CreateTaskAction(BaseModel):
    type: Literal["create_task"] = "create_task"
    title: str
    goal: str
    steps: list[str] = []


class QueueStepsAction(BaseModel):
    type: Literal["queue_steps"] = "queue_steps"
    taskId: str
    steps: list[str] = Field(min_length=1)


class RunCommandAction(BaseModel):
    type: Literal["run_command"] = "run_command"
    command: str = Field(min_length=1)


class RequestApprovalAction(BaseModel):
    type: Literal["request_approval"] = "request_approval"
    command: str = Field(min_length=1)
    reason: str = ""


class RequestUserAction(BaseModel):
    type: Literal["request_user"] = "request_user"
    reason: str = Field(min_length=1)


class RetryAction(BaseModel):
    type: Literal["retry"] = "retry"
    taskId: str
    step: Optional[str] = None


class RerouteAction(BaseModel):
    type: Literal["reroute"] = "reroute"
    taskId: str
    step: str
    provider: str


class CompleteTaskAction(BaseModel):
    type: Literal["complete_task"] = "complete_task"
    taskId: Optional[str] = None
    reason: str = ""


class CancelAction(BaseModel):
    type: Literal["cancel"] = "cancel"
    runId: Optional[str] = None


ControllerAction = Annotated[
    Union[
        AnswerAction,
        CreateTaskAction,
        QueueStepsAction,
        RunCommandAction,
        RequestApprovalAction,
        RequestUserAction,
        RetryAction,
        RerouteAction,
        CompleteTaskAction,
        CancelAction,
    ],
    Field(discriminator="type"),
]

# The closed set of action types, for prompt synchronization (Phase 3).
ACTION_TYPES: tuple[str, ...] = (
    "answer",
    "create_task",
    "queue_steps",
    "run_command",
    "request_approval",
    "request_user",
    "retry",
    "reroute",
    "complete_task",
    "cancel",
)


class ControllerMessage(BaseModel):
    summary: str = ""
    details: list[str] = []


class ControllerResult(BaseModel):
    schemaVersion: Literal["1"] = "1"
    kind: Literal["controller_result"] = "controller_result"
    message: ControllerMessage = ControllerMessage()
    action: ControllerAction


class ParseMeta(BaseModel):
    source: Literal["v1", "none"] = "none"
    blocks: int = 0  # number of CLITC_RESULT_V1 blocks seen (>1 is a misbehaviour signal)


def result_contract_prompt() -> str:
    """The output-contract instruction for controller prompts, generated from the
    action schema so the prompt and the validator never drift (Phase 3). Replaces
    the legacy ``agentflow-*`` generation instructions in normal operation."""
    actions = ", ".join(ACTION_TYPES)
    return (
        "OUTPUT CONTRACT. After any human-readable reasoning, end your reply with "
        "exactly ONE deterministic result block and nothing after it:\n"
        f"{OPEN}\n"
        '{"schemaVersion":"1","kind":"controller_result",'
        '"message":{"summary":"<one line>","details":["<short>"]},'
        '"action":{"type":"<one allowed action>"}}\n'
        f"{CLOSE}\n"
        f"Allowed action types: {actions}. Action shapes: "
        '{"type":"answer"}; '
        '{"type":"create_task","title":"<t>","goal":"<g>","steps":["codex_spec"]}; '
        '{"type":"queue_steps","taskId":"<id|latest>","steps":["claude_implement"]}; '
        '{"type":"run_command","command":"npm test"}; '
        '{"type":"complete_task","reason":"<why>"}; '
        '{"type":"request_user","reason":"<why>"}. '
        "Valid steps: codex_spec, claude_implement, gemini_qa, codex_review, claude_fix "
        '(or ["full"]). The block is parsed as JSON and validated; if it is invalid, '
        "no action is taken."
    )


def strip_result_block(text: str) -> str:
    """Remove every CLITC_RESULT_V1 block so the result JSON never renders as prose."""
    return _BLOCK_RE.sub("", text or "")


def parse_controller_result(text: str) -> tuple[Optional[ControllerResult], Optional[FailureRecord], ParseMeta]:
    """Extract + validate the single authoritative controller result from ``text``.

    Returns ``(result, failure, meta)``:
    - ``(result, None, meta)`` when a valid CLITC_RESULT_V1 block is present.
    - ``(None, None, meta(source="none"))`` when NO block is present (caller may try
      the legacy fallback).
    - ``(None, failure, meta)`` when a block is present but oversized / malformed /
      schema-invalid — the caller must surface the failure and mutate NO state.
    """
    blocks = _BLOCK_RE.findall(text or "")
    meta = ParseMeta(source="none" if not blocks else "v1", blocks=len(blocks))
    if not blocks:
        return None, None, meta

    raw = blocks[-1].strip()  # last block is authoritative
    if len(raw.encode("utf-8")) > MAX_RESULT_BYTES:
        return (
            None,
            FailureRecord(title="Controller result too large", summary=f"Result exceeds {MAX_RESULT_BYTES} bytes."),
            meta,
        )
    try:
        data = json.loads(raw)
    except ValueError:
        return (
            None,
            FailureRecord(title="Malformed controller result", summary="The CLITC_RESULT_V1 block is not valid JSON."),
            meta,
        )
    if not isinstance(data, dict):
        return None, FailureRecord(title="Malformed controller result", summary="Expected a JSON object."), meta
    version = str(data.get("schemaVersion", PROTOCOL_VERSION))
    if version != PROTOCOL_VERSION:
        return (
            None,
            FailureRecord(
                title="Unsupported controller result version",
                summary=f"Version {version!r} (expected {PROTOCOL_VERSION!r}).",
            ),
            meta,
        )
    try:
        return ControllerResult.model_validate(data), None, meta
    except ValidationError as exc:
        return (
            None,
            FailureRecord(
                title="Invalid controller result", summary=f"Failed validation: {exc.error_count()} error(s)."
            ),
            meta,
        )
