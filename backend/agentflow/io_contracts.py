"""Typed input/output contracts (I/O rebuild, Phase 1).

Two planes are defined here as versioned, validated models:

- **Input plane** — :class:`InputSubmission`: one typed model for every input
  surface (controller chat, provider chat, task input). Destination and intent are
  explicit fields, never encoded inside free-form text.
- **Operational-event plane** — :class:`OutputEventEnvelope` + a discriminated
  ``payload`` union: the application-owned event contract. This replaces the open
  ``data: dict`` shape as the *authoritative* contract; ``event_bus`` continues to
  emit the legacy flat dict during migration, and :func:`validate_event` is the
  boundary validator the typed pipeline uses.

The deterministic-result plane (controller results + summaries) lives in
:mod:`agentflow.controller_protocol` and :mod:`agentflow.contracts`.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, ValidationError

SCHEMA_VERSION = "1"


# ============================================================ INPUT PLANE


class FileReference(BaseModel):
    kind: Literal["file"] = "file"
    path: str


class FolderReference(BaseModel):
    kind: Literal["folder"] = "folder"
    path: str


class DiffReference(BaseModel):
    kind: Literal["diff"] = "diff"
    path: str
    staged: bool = False


class TaskArtifactReference(BaseModel):
    kind: Literal["task_artifact"] = "task_artifact"
    taskId: str
    name: str


class RunReference(BaseModel):
    kind: Literal["run"] = "run"
    runId: str


class EventRangeReference(BaseModel):
    kind: Literal["event_range"] = "event_range"
    fromEventId: int
    toEventId: int


InputReference = Annotated[
    Union[FileReference, FolderReference, DiffReference, TaskArtifactReference, RunReference, EventRangeReference],
    Field(discriminator="kind"),
]


class ControllerDestination(BaseModel):
    kind: Literal["controller"] = "controller"


class ProviderDestination(BaseModel):
    kind: Literal["provider"] = "provider"
    provider: str


class TaskDestination(BaseModel):
    kind: Literal["task"] = "task"
    taskId: str
    intent: Literal["continue", "clarify", "retry", "fix", "reroute", "ask"] = "continue"


InputDestination = Annotated[
    Union[ControllerDestination, ProviderDestination, TaskDestination],
    Field(discriminator="kind"),
]


class InputContent(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    references: list[InputReference] = []


class InputContext(BaseModel):
    taskId: Optional[str] = None
    step: Optional[str] = None
    provider: Optional[str] = None
    orchestrationMode: Optional[str] = None


class InputBehavior(BaseModel):
    submitMode: Literal["message", "create_task", "continue", "retry", "reroute"] = "message"


class InputSubmission(BaseModel):
    schemaVersion: Literal["1"] = "1"
    id: str
    workspaceId: str
    destination: InputDestination
    content: InputContent
    context: InputContext = InputContext()
    behavior: InputBehavior = InputBehavior()
    createdAt: str


# ===================================================== OPERATIONAL EVENT PLANE
# Discriminated payloads, keyed by the envelope's ``type``. This is the typed
# contract that replaces the open ``data`` dict as the long-term shape.


class NarrativeDeltaPayload(BaseModel):
    type: Literal["narrative.delta"] = "narrative.delta"
    text: str


class NarrativeCompletedPayload(BaseModel):
    type: Literal["narrative.completed"] = "narrative.completed"
    text: str = ""


class CommandStartedPayload(BaseModel):
    type: Literal["command.started"] = "command.started"
    command: str


class CommandOutputPayload(BaseModel):
    type: Literal["command.output"] = "command.output"
    text: str


class CommandCompletedPayload(BaseModel):
    type: Literal["command.completed"] = "command.completed"
    exitCode: Optional[int] = None
    durationMs: Optional[int] = None
    status: Literal["succeeded", "failed", "cancelled", "error"] = "succeeded"


class TaskStatePayload(BaseModel):
    type: Literal["task.state"] = "task.state"
    taskId: str
    state: str


class QueueStatePayload(BaseModel):
    type: Literal["queue.state"] = "queue.state"
    activeCount: int = 0


class ApprovalRequestedPayload(BaseModel):
    type: Literal["approval.requested"] = "approval.requested"
    approvalId: str
    action: str
    reason: str = ""


class ApprovalResolvedPayload(BaseModel):
    type: Literal["approval.resolved"] = "approval.resolved"
    approvalId: str
    approved: bool


class FailurePayload(BaseModel):
    type: Literal["failure"] = "failure"
    title: str
    summary: str = ""


class CancellationPayload(BaseModel):
    type: Literal["cancellation"] = "cancellation"
    runId: Optional[str] = None


class SummaryReadyPayload(BaseModel):
    type: Literal["summary.ready"] = "summary.ready"
    kind: str  # a contracts.py summary kind (task_summary/test_summary/…)


EventPayload = Annotated[
    Union[
        NarrativeDeltaPayload,
        NarrativeCompletedPayload,
        CommandStartedPayload,
        CommandOutputPayload,
        CommandCompletedPayload,
        TaskStatePayload,
        QueueStatePayload,
        ApprovalRequestedPayload,
        ApprovalResolvedPayload,
        FailurePayload,
        CancellationPayload,
        SummaryReadyPayload,
    ],
    Field(discriminator="type"),
]


class OutputEventEnvelope(BaseModel):
    schemaVersion: Literal["1"] = "1"
    id: str
    workspaceId: str
    createdAt: str
    taskId: Optional[str] = None
    runId: Optional[str] = None
    chatId: Optional[str] = None
    messageId: Optional[str] = None
    queueItemId: Optional[str] = None
    approvalId: Optional[str] = None
    provider: Optional[str] = None
    step: Optional[str] = None
    channel: Optional[Literal["assistant", "controller", "stdout", "stderr", "system"]] = None
    sequence: Optional[int] = None
    redacted: bool = False
    truncated: bool = False
    payload: EventPayload


def validate_event(data: dict) -> tuple[Optional[OutputEventEnvelope], Optional[str]]:
    """Validate a raw event dict against the typed envelope. Returns
    ``(envelope, None)`` or ``(None, error_message)`` — never raises."""
    try:
        return OutputEventEnvelope.model_validate(data), None
    except ValidationError as exc:
        return None, f"{exc.error_count()} validation error(s)"


def validate_submission(data: dict) -> tuple[Optional[InputSubmission], Optional[str]]:
    """Validate a raw input submission. Returns ``(submission, None)`` or
    ``(None, error_message)`` — never raises."""
    try:
        return InputSubmission.model_validate(data), None
    except ValidationError as exc:
        return None, f"{exc.error_count()} validation error(s)"
