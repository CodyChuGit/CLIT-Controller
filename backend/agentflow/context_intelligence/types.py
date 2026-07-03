"""Typed contracts for the Context Intelligence pipeline (Pydantic v2).

``ContextPackage`` is the selected raw material; ``PromptPackage`` is the
rendered, ordered result. Field names are camelCase, matching the repo's API
convention (``controller_protocol``, ``models``).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

CompressorName = Literal["simple", "headroom", "none"]


class UserTask(BaseModel):
    text: str = Field(min_length=1)
    maxTokens: Optional[int] = Field(default=None, ge=1)


class BehaviorPolicy(BaseModel):
    """Ponytail-derived behavior policy. ``block`` is empty when the level is off."""

    level: str = "off"
    block: str = ""


class RepoMapEntry(BaseModel):
    path: str
    size: int = 0
    language: str = ""
    symbols: list[str] = []


class RepoMap(BaseModel):
    root: str = ""
    entries: list[RepoMapEntry] = []
    fileCount: int = 0
    truncated: bool = False


class FileContext(BaseModel):
    path: str
    excerpt: str = ""
    reasons: list[str] = []
    score: float = 0.0
    excerptTruncated: bool = False


class RejectedCandidate(BaseModel):
    path: str
    score: float = 0.0
    reason: str = ""


class ContextSelection(BaseModel):
    selected: list[FileContext] = []
    rejected: list[RejectedCandidate] = []


class GitContext(BaseModel):
    isRepo: bool = False
    branch: str = ""
    changedFiles: list[str] = []
    diff: str = ""
    truncated: bool = False


class LogContext(BaseModel):
    summary: str = ""
    entryCount: int = 0
    sources: list[str] = []


class MemoryContext(BaseModel):
    chatLines: list[str] = []
    taskLines: list[str] = []


class SessionDigest(BaseModel):
    text: str = ""
    sources: list[str] = []


class ContextPackage(BaseModel):
    task: UserTask
    policy: BehaviorPolicy = BehaviorPolicy()
    repoMap: RepoMap = RepoMap()
    selection: ContextSelection = ContextSelection()
    git: GitContext = GitContext()
    logs: LogContext = LogContext()
    memory: MemoryContext = MemoryContext()
    digest: SessionDigest = SessionDigest()
    projectRules: str = ""


class TokenBudget(BaseModel):
    maxTokens: Optional[int] = None
    perFileChars: int = 6000
    diffChars: int = 20_000


class CompressionResult(BaseModel):
    section: str = ""
    compressor: CompressorName = "none"
    charsBefore: int = 0
    charsAfter: int = 0
    applied: bool = False


class PromptSection(BaseModel):
    name: str
    content: str = ""


class PromptPackage(BaseModel):
    sections: list[PromptSection] = []
    text: str = ""


class TokenUsage(BaseModel):
    tokensBefore: int = 0
    tokensAfter: int = 0
    counter: str = "estimate"
    savingsPct: float = 0.0


class OptimizationReport(BaseModel):
    id: str
    kind: Literal["preview", "benchmark"] = "preview"
    createdAt: str = ""
    task: str = ""
    policyLevel: str = "off"
    selectedFiles: list[FileContext] = []
    rejectedCandidates: list[RejectedCandidate] = []
    gitChangedFiles: list[str] = []
    sectionOrder: list[str] = []
    tokenUsage: TokenUsage = TokenUsage()
    compression: list[CompressionResult] = []
    digest: SessionDigest = SessionDigest()
    promptPreview: str = ""
    benchmark: list["BenchmarkResult"] = []


class BenchmarkCase(BaseModel):
    name: str = "workspace"
    task: str
    mustKeep: list[str] = []


class BenchmarkResult(BaseModel):
    strategy: Literal["naive", "ranked", "ranked_compressed"]
    tokens: int = 0
    counter: str = "estimate"
    selectedFileCount: int = 0
    mustKeepTotal: int = 0
    mustKeepRetained: int = 0
    retention: float = 1.0
    missing: list[str] = []
