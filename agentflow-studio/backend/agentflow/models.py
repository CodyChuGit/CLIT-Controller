"""Pydantic request models for the API."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Health = Literal["green", "yellow", "red"]
OrchestrationMode = Literal["maximum_quality", "balanced", "budget_saver", "manual_approval"]

ORCHESTRATION_MODES: list[str] = [
    "maximum_quality",
    "balanced",
    "budget_saver",
    "manual_approval",
]


class WorkspaceRequest(BaseModel):
    path: str = Field(min_length=1)


class FileRequest(BaseModel):
    path: str


class AgentActionRequest(BaseModel):
    id: str


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    goal: str = Field(min_length=1)


class RunStepRequest(BaseModel):
    confirm: bool = False


class RunFullRequest(BaseModel):
    confirm: bool = False


class StopRequest(BaseModel):
    runId: Optional[str] = None


class ModeUpdateRequest(BaseModel):
    mode: OrchestrationMode


class ProviderHealthRequest(BaseModel):
    provider: str
    health: Health


class RoutingConfig(BaseModel):
    orchestrator: str = "antigravity"
    pm: str = "codex"
    engineer: str = "claude"
    qa: str = "antigravity"


class SettingsUpdateRequest(BaseModel):
    routing: Optional[RoutingConfig] = None
    commandTemplates: Optional[dict[str, str]] = None


class GitPathRequest(BaseModel):
    path: Optional[str] = None  # None means "all" for staging


class GitCommitRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
