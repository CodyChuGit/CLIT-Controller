"""Native compression interface with exactly two implementations.

Only bulky context bodies (file excerpts, logs, diffs) go through this —
the pipeline never compresses the user task, file paths, symbol names,
error messages, line numbers, or the Ponytail policy block.
"""

from __future__ import annotations

import re
from typing import Protocol

from .. import headroom_service
from .types import CompressionResult, CompressorName


class Compressor(Protocol):
    name: CompressorName

    async def compress(self, text: str, instructions: str = "") -> str: ...


# --------------------------------------------------------- deterministic pass

_MAX_CONSECUTIVE_DUPES = 2
_MAX_LINES = 400  # per body; beyond this the middle is elided with a marker
_MAX_RESCUED_ERRORS = 50

# Preservation guarantee: error messages (and their line numbers) must survive
# compression, so elision rescues middle lines that look like failures.
_ERROR_RE = re.compile(r"(?i)\b(error|exception|traceback|failed|fatal|panic)\b")


def _collapse_blank_runs(lines: list[str]) -> list[str]:
    out: list[str] = []
    blanks = 0
    for line in lines:
        if line.strip() == "":
            blanks += 1
            if blanks > 1:
                continue
            out.append("")
        else:
            blanks = 0
            out.append(line.rstrip())
    return out


def _fold_duplicates(lines: list[str]) -> list[str]:
    out: list[str] = []
    run_start = 0
    for i in range(len(lines) + 1):
        if i < len(lines) and lines[i] == lines[run_start]:
            continue
        run_len = i - run_start
        if lines[run_start].strip() == "":
            out.extend(lines[run_start:i])
        elif run_len > _MAX_CONSECUTIVE_DUPES:
            out.extend(lines[run_start : run_start + _MAX_CONSECUTIVE_DUPES])
            out.append(f"[… {run_len - _MAX_CONSECUTIVE_DUPES} more identical lines]")
        else:
            out.extend(lines[run_start:i])
        run_start = i
    return out


def _truncate_long_runs(lines: list[str]) -> list[str]:
    if len(lines) <= _MAX_LINES:
        return lines
    head = lines[: _MAX_LINES * 3 // 4]
    tail = lines[-_MAX_LINES // 4 :]
    middle = lines[len(head) : len(lines) - len(tail)]
    rescued = [line for line in middle if _ERROR_RE.search(line)][:_MAX_RESCUED_ERRORS]
    elided = len(middle) - len(rescued)
    return [*head, *rescued, f"[… {elided} more lines]", *tail]


def simple_compress_text(text: str) -> str:
    """Pure, fully deterministic: blank-run collapsing, duplicate-line folding,
    long-run truncation with ``[… N more lines]`` markers."""
    if not text:
        return text
    lines = _collapse_blank_runs(text.splitlines())
    lines = _fold_duplicates(lines)
    lines = _truncate_long_runs(lines)
    return "\n".join(lines)


class SimpleDeterministicCompressor:
    name: CompressorName = "simple"

    async def compress(self, text: str, instructions: str = "") -> str:
        return simple_compress_text(text)


class HeadroomCompressor:
    """The existing in-process ``headroom_service`` behind the interface —
    already fail-open, threaded, and stats-tracked. No second adapter."""

    name: CompressorName = "headroom"

    async def compress(self, text: str, instructions: str = "") -> str:
        return await headroom_service.compress_context(text, instructions)


async def compress_body(section: str, text: str, instructions: str = "") -> tuple[str, list[CompressionResult]]:
    """Run one bulky body through both implementations (deterministic pass first,
    Headroom second — each fail-open by construction) and record what happened."""
    results: list[CompressionResult] = []
    current = text
    for compressor in (SimpleDeterministicCompressor(), HeadroomCompressor()):
        before = len(current)
        current = await compressor.compress(current, instructions)
        results.append(
            CompressionResult(
                section=section,
                compressor=compressor.name,
                charsBefore=before,
                charsAfter=len(current),
                applied=len(current) < before,
            )
        )
    return current, results
