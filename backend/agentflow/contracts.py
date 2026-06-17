"""Pillar 5 — deterministic, versioned output contracts.

These Pydantic models are the **deterministic semantic layer** (docs/PILLARS.md,
Pillar 5): the structured meaning of controller decisions, command/test results,
summaries, approvals, and agent hand-offs. They sit between the canonical event
envelope (state_store/event_bus) and the frontend presentation model.

Why this exists:
- Controller/agent decisions are validated records, not prose guessed with regex.
- Summaries have one stable, versioned shape that can be styled, replayed, indexed,
  compared, and compressed for token-efficient hand-offs.
- The UI selects components by `kind`, not by sniffing text.

Rules:
- Every contract carries a `version` and a `kind` discriminator.
- Unknown/invalid payloads fail **safely** via `validate()` (a structured failure),
  never a crash or an infinite correction loop.
- Adding/altering a contract is a versioned change; readers must tolerate unknown
  variants by rejecting them safely.
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, ValidationError

CONTRACT_VERSION = "1"


class _Contract(BaseModel):
    version: str = CONTRACT_VERSION


# ----------------------------------------------------------- controller decisions
# The controller emits fenced directive blocks (see chat_directives.py); these are
# their validated structured forms.


class TaskDirective(_Contract):
    kind: Literal["task"] = "task"
    title: str
    goal: str
    queueSteps: Optional[list[str]] = None


class QueueDirective(_Contract):
    kind: Literal["queue"] = "queue"
    taskRef: str
    steps: list[str]


class RunDirective(_Contract):
    kind: Literal["run"] = "run"
    command: str


class DoneDirective(_Contract):
    kind: Literal["done"] = "done"
    reason: str


class NeedsUserDirective(_Contract):
    kind: Literal["needs_user"] = "needs_user"
    reason: str


ControllerDirective = Union[TaskDirective, QueueDirective, RunDirective, DoneDirective, NeedsUserDirective]


# --------------------------------------------------------------- results & summaries


class CommandSummary(_Contract):
    kind: Literal["command_summary"] = "command_summary"
    command: str
    status: Literal["running", "succeeded", "failed", "cancelled", "error"]
    exitCode: Optional[int] = None
    durationMs: Optional[int] = None
    taskId: Optional[str] = None
    summary: str = ""


class TestFailure(BaseModel):
    test: str
    summary: str
    source: Optional[str] = None


class OutputRef(BaseModel):
    """Reference to full output in the canonical event ledger (token-efficiency:
    pass the compact summary, retrieve full detail only when needed)."""

    runId: Optional[str] = None
    fromEventId: Optional[int] = None
    toEventId: Optional[int] = None


class TestSummary(_Contract):
    kind: Literal["test_summary"] = "test_summary"
    status: Literal["passed", "failed"]
    passed: int = 0
    failed: int = 0
    failures: list[TestFailure] = []
    fullOutputRef: Optional[OutputRef] = None


class FailureRecord(_Contract):
    kind: Literal["failure"] = "failure"
    title: str
    summary: str
    userActionRequired: bool = False
    technicalDetailsRef: Optional[str] = None


class ApprovalRequest(_Contract):
    kind: Literal["approval_request"] = "approval_request"
    action: str
    reason: str = ""
    provider: Optional[str] = None
    taskId: Optional[str] = None


class ChangeItem(BaseModel):
    area: str
    description: str


class VerificationItem(BaseModel):
    command: str
    status: Literal["passed", "failed", "skipped"]


class TaskSummary(_Contract):
    kind: Literal["task_summary"] = "task_summary"
    status: Literal["completed", "failed", "needs_user", "in_progress"]
    title: str
    summary: str
    changes: list[ChangeItem] = []
    verification: list[VerificationItem] = []
    limitations: list[str] = []


class AgentHandoff(_Contract):
    kind: Literal["agent_handoff"] = "agent_handoff"
    fromStep: Optional[str] = None
    toStep: str
    provider: str
    summary: str
    artifacts: list[str] = []


class TokenEfficiencyReport(_Contract):
    kind: Literal["token_efficiency_report"] = "token_efficiency_report"
    headroomApplied: bool
    proxyUrl: Optional[str] = None
    profile: Optional[str] = None
    # Measured by the proxy; null here means "not measured by AgentComposer —
    # verify with `headroom agent-savings --check-perf`" (never fabricated).
    originalTokens: Optional[int] = None
    optimizedTokens: Optional[int] = None
    tokensSaved: Optional[int] = None
    compressionRatio: Optional[float] = None
    note: str = ""


# Registry of every validatable contract, keyed by its `kind`.
_REGISTRY: dict[str, type[_Contract]] = {
    "task": TaskDirective,
    "queue": QueueDirective,
    "run": RunDirective,
    "done": DoneDirective,
    "needs_user": NeedsUserDirective,
    "command_summary": CommandSummary,
    "test_summary": TestSummary,
    "failure": FailureRecord,
    "approval_request": ApprovalRequest,
    "task_summary": TaskSummary,
    "agent_handoff": AgentHandoff,
    "token_efficiency_report": TokenEfficiencyReport,
}


def validate(kind: str, data: dict) -> tuple[Optional[_Contract], Optional[FailureRecord]]:
    """Validate ``data`` against the contract for ``kind``.

    Returns ``(model, None)`` on success or ``(None, FailureRecord)`` on an unknown
    kind, a version this reader doesn't support, or a schema violation. Never raises
    for bad input — callers get a structured failure to surface, not an exception.
    """
    model_cls = _REGISTRY.get(kind)
    if model_cls is None:
        return None, FailureRecord(
            title="Unknown contract kind",
            summary=f"No reader for contract kind {kind!r}.",
        )
    version = str(data.get("version", CONTRACT_VERSION))
    if version != CONTRACT_VERSION:
        return None, FailureRecord(
            title="Unsupported contract version",
            summary=f"{kind!r} contract version {version!r} is not supported (expected {CONTRACT_VERSION!r}).",
        )
    try:
        return model_cls.model_validate(data), None
    except ValidationError as exc:
        return None, FailureRecord(
            title="Invalid structured output",
            summary=f"{kind!r} contract failed validation: {exc.error_count()} error(s).",
            technicalDetailsRef=None,
        )
