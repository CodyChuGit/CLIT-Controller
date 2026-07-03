"""Local benchmark: three context strategies on the same BenchmarkCase inputs.

1. ``naive``             — top-N whole files by simple term match, no compression
2. ``ranked``            — full ranking pipeline, per-file excerpts, no compression
3. ``ranked_compressed`` — strategy 2 plus the compression interface

Cases are built from local workspace state only; no network, no models.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from .. import workspace
from ..process_runner import now_iso
from . import file_ranker, metrics, pipeline, prompt_builder
from .types import BenchmarkCase, BenchmarkResult, ContextPackage, OptimizationReport, UserTask

NAIVE_TOP_N = 8
MUST_KEEP_SYMBOLS = 5
MUST_KEEP_ERROR_LINES = 3


def build_case(package: ContextPackage) -> BenchmarkCase:
    """Deterministic must-keep strings from the workspace's own state: the task
    text, named symbols of selected files, and error lines from the logs."""
    must_keep: list[str] = [package.task.text]
    by_path = {e.path: e for e in package.repoMap.entries}
    symbols: list[str] = []
    for selected in package.selection.selected:
        entry = by_path.get(selected.path)
        if entry is not None:
            symbols.extend(entry.symbols[:2])
    must_keep.extend(dict.fromkeys(symbols[:MUST_KEEP_SYMBOLS]))
    error_lines = [line for line in package.logs.summary.splitlines() if "error" in line.lower()]
    must_keep.extend(error_lines[:MUST_KEEP_ERROR_LINES])
    return BenchmarkCase(name="workspace", task=package.task.text, mustKeep=[m for m in must_keep if m])


def _naive_prompt(workspace_path: Path, package: ContextPackage) -> tuple[str, int]:
    """Whole files by path term match only — the fat baseline."""
    terms = file_ranker.task_terms(package.task.text)
    hits = [e.path for e in package.repoMap.entries if any(t in e.path.lower() for t in terms)]
    parts = [f"USER TASK:\n{package.task.text}"]
    for rel_path in hits[:NAIVE_TOP_N]:
        try:
            content: str = workspace.read_text_file(workspace_path, rel_path)["content"]
        except (PermissionError, FileNotFoundError, ValueError, OSError):
            continue
        parts.append(f"### {rel_path}\n{content}")
    return "\n\n".join(parts), min(len(hits), NAIVE_TOP_N)


def _result(strategy: str, text: str, file_count: int, case: BenchmarkCase) -> BenchmarkResult:
    tokens, counter = metrics.count_tokens(text)
    missing = [m for m in case.mustKeep if m not in text]
    kept = len(case.mustKeep) - len(missing)
    return BenchmarkResult(
        strategy=strategy,  # type: ignore[arg-type]
        tokens=tokens,
        counter=counter,
        selectedFileCount=file_count,
        mustKeepTotal=len(case.mustKeep),
        mustKeepRetained=kept,
        retention=round(kept / len(case.mustKeep), 3) if case.mustKeep else 1.0,
        missing=missing,
    )


async def run_benchmark(workspace_path: Path, task: UserTask) -> OptimizationReport:
    """Compare the three strategies on one case; returns a persistable report."""
    package = await pipeline.build_context_package(workspace_path, task)
    case = build_case(package)

    naive_text, naive_files = _naive_prompt(workspace_path, package)
    ranked_prompt = prompt_builder.build_prompt_package(package)
    compressed, compression_results = await pipeline.compress_package(package)
    compressed_prompt = prompt_builder.build_prompt_package(compressed)

    results = [
        _result("naive", naive_text, naive_files, case),
        _result("ranked", ranked_prompt.text, len(package.selection.selected), case),
        _result("ranked_compressed", compressed_prompt.text, len(compressed.selection.selected), case),
    ]
    return OptimizationReport(
        id=uuid.uuid4().hex,
        kind="benchmark",
        createdAt=now_iso(),
        task=task.text,
        policyLevel=package.policy.level,
        selectedFiles=[f.model_copy(update={"excerpt": ""}) for f in package.selection.selected],
        rejectedCandidates=package.selection.rejected,
        gitChangedFiles=package.git.changedFiles,
        sectionOrder=list(prompt_builder.SECTION_ORDER),
        tokenUsage=metrics.usage(naive_text, compressed_prompt.text),
        compression=compression_results,
        digest=package.digest,
        benchmark=results,
    )
