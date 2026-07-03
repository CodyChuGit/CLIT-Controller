"""The context intelligence pipeline: task in → explained, measured report out.

Async because its seams are async (``git_service``, ``headroom_service``).
Compression touches only bulky bodies — the user task, paths, symbols, and
the Ponytail policy block never pass through a compressor.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from .. import workspace
from ..process_runner import now_iso
from . import behavior, compression, file_ranker, git_context, log_context, memory, metrics, prompt_builder, repo_map
from .types import (
    CompressionResult,
    ContextPackage,
    OptimizationReport,
    PromptPackage,
    UserTask,
)

PROJECT_RULES_FILES = ("CLAUDE.md", "AGENTS.md")
PROJECT_RULES_CHARS = 2000
PROMPT_PREVIEW_CHARS = 20_000


def _project_rules(workspace_path: Path) -> str:
    for name in PROJECT_RULES_FILES:
        try:
            content: str = workspace.read_text_file(workspace_path, name)["content"]
        except (PermissionError, FileNotFoundError, ValueError, OSError):
            continue
        if len(content) > PROJECT_RULES_CHARS:
            content = content[:PROJECT_RULES_CHARS] + "\n[… project rules trimmed]"
        return f"Project rules ({name}):\n{content}"
    return ""


async def build_context_package(workspace_path: Path, task: UserTask) -> ContextPackage:
    """Assemble the uncompressed raw material (steps 1–7 of the pipeline)."""
    policy = behavior.build_policy()
    rmap = repo_map.build_repo_map(workspace_path)
    git = await git_context.build_git_context(workspace_path)
    selection = file_ranker.rank_files(workspace_path, task.text, rmap, git.changedFiles)
    logs = log_context.build_log_context()
    mem = memory.build_memory_context(workspace_path)
    return ContextPackage(
        task=task,
        policy=policy,
        repoMap=rmap,
        selection=selection,
        git=git,
        logs=logs,
        memory=mem,
        digest=memory.build_session_digest(mem),
        projectRules=_project_rules(workspace_path),
    )


async def compress_package(package: ContextPackage) -> tuple[ContextPackage, list[CompressionResult]]:
    """Compress only the bulky bodies: file excerpts, log summary, git diff."""
    compressed = package.model_copy(deep=True)
    # The task text here is the relevance QUERY for compression (protected
    # verbatim by headroom's user-role handling, like orchestrator_consult) —
    # it is never itself compressed; the prompt renders it from package.task.
    instructions = package.task.text
    results: list[CompressionResult] = []

    for file_ctx in compressed.selection.selected:
        file_ctx.excerpt, file_results = await compression.compress_body(
            f"file:{file_ctx.path}", file_ctx.excerpt, instructions
        )
        results.extend(file_results)
    compressed.logs.summary, log_results = await compression.compress_body(
        "logs", compressed.logs.summary, instructions
    )
    results.extend(log_results)
    compressed.git.diff, diff_results = await compression.compress_body("git_diff", compressed.git.diff, instructions)
    results.extend(diff_results)
    return compressed, results


def _build_report(
    package: ContextPackage,
    prompt: PromptPackage,
    token_usage_before: str,
    compression_results: list[CompressionResult],
) -> OptimizationReport:
    return OptimizationReport(
        id=uuid.uuid4().hex,
        kind="preview",
        createdAt=now_iso(),
        task=package.task.text,
        policyLevel=package.policy.level,
        selectedFiles=package.selection.selected,
        rejectedCandidates=package.selection.rejected,
        gitChangedFiles=package.git.changedFiles,
        sectionOrder=list(prompt_builder.SECTION_ORDER),
        tokenUsage=metrics.usage(token_usage_before, prompt.text),
        compression=compression_results,
        digest=package.digest,
        promptPreview=prompt.text[:PROMPT_PREVIEW_CHARS],
    )


async def run_preview(workspace_path: Path, task: UserTask) -> OptimizationReport:
    """Full pipeline: build, compress, render, measure — one optimization report.

    Selected files / reasons / digest in the report come from the UNcompressed
    package (they explain the selection); the preview and after-tokens come from
    the compressed render.
    """
    package = await build_context_package(workspace_path, task)
    prompt_before = prompt_builder.build_prompt_package(package)
    compressed, compression_results = await compress_package(package)
    prompt_after = prompt_builder.build_prompt_package(compressed)
    report = _build_report(package, prompt_after, prompt_before.text, compression_results)
    if task.maxTokens is not None and report.tokenUsage.tokensAfter > task.maxTokens:
        report.promptPreview = (
            f"[prompt exceeds maxTokens={task.maxTokens}: {report.tokenUsage.tokensAfter} tokens]\n"
            + report.promptPreview
        )
    return report
