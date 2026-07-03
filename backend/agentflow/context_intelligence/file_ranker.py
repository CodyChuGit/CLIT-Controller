"""Deterministic file ranking: task terms vs paths/symbols/extensions/git state.

Every selected file carries human-readable reasons; the top rejected
candidates are reported with why they lost. Never dumps the whole repo —
selection is capped and excerpts are trimmed per file.
"""

from __future__ import annotations

import re
from pathlib import Path

from .. import workspace
from .types import ContextSelection, FileContext, RejectedCandidate, RepoMap

TOP_N_FILES = 8
TOP_N_REJECTED = 8
EXCERPT_CHARS = 6000
MIN_SCORE = 1.0

_STOPWORDS = frozenset(
    "the a an and or for with from into onto this that these those is are was be been "
    "add fix make use using new to of in on at it its as by do does not".split()
)

_EXT_HINTS = {
    "python": {".py"},
    "typescript": {".ts", ".tsx"},
    "javascript": {".js", ".jsx"},
    "frontend": {".ts", ".tsx", ".js", ".jsx", ".css", ".html"},
    "react": {".tsx", ".jsx"},
    "css": {".css"},
    "docs": {".md"},
    "test": {".py", ".ts", ".tsx"},
}


def task_terms(text: str) -> list[str]:
    """Lowercased, deduplicated task terms (stopwords and short tokens dropped)."""
    tokens = re.split(r"[^a-z0-9_]+", text.lower())
    return list(dict.fromkeys(t for t in tokens if len(t) >= 3 and t not in _STOPWORDS))


def _score_entry(path: str, symbols: list[str], terms: list[str], changed: set[str]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    path_lower = path.lower()
    stem = Path(path).stem.lower()

    path_hits = [t for t in terms if t in path_lower]
    if path_hits:
        score += 2.0 * len(path_hits) + sum(2.0 for t in path_hits if t == stem)
        reasons.append("task terms in path: " + ", ".join(path_hits[:4]))

    symbol_hits = sorted({s for s in symbols for t in terms if t in s.lower()})
    if symbol_hits:
        score += 1.5 * len(symbol_hits)
        reasons.append("matching symbols: " + ", ".join(symbol_hits[:4]))

    ext = Path(path).suffix.lower()
    ext_hits = [t for t in terms if ext in _EXT_HINTS.get(t, set())]
    if ext_hits:
        score += 0.5
        reasons.append(f"extension {ext} matches task hint '{ext_hits[0]}'")

    if path in changed:
        score += 3.0
        reasons.append("changed in git working tree")

    return score, reasons


def _excerpt(workspace_path: Path, rel_path: str) -> tuple[str, bool]:
    try:
        result = workspace.read_text_file(workspace_path, rel_path)
    except (PermissionError, FileNotFoundError, ValueError, OSError):
        return "", False
    content: str = result["content"]
    if len(content) <= EXCERPT_CHARS:
        return content, bool(result["truncated"])
    return content[:EXCERPT_CHARS] + "\n[… excerpt trimmed]", True


def rank_files(
    workspace_path: Path,
    task_text: str,
    repo_map: RepoMap,
    changed_files: list[str],
    top_n: int = TOP_N_FILES,
    with_excerpts: bool = True,
) -> ContextSelection:
    terms = task_terms(task_text)
    changed = set(changed_files)

    scored: list[tuple[float, str, list[str]]] = []
    for entry in repo_map.entries:
        score, reasons = _score_entry(entry.path, entry.symbols, terms, changed)
        if score > 0:
            scored.append((score, entry.path, reasons))
    scored.sort(key=lambda item: (-item[0], item[1]))

    selected: list[FileContext] = []
    for score, path, reasons in scored[:top_n]:
        if score < MIN_SCORE:
            break
        excerpt, trimmed = _excerpt(workspace_path, path) if with_excerpts else ("", False)
        selected.append(
            FileContext(path=path, excerpt=excerpt, reasons=reasons, score=round(score, 2), excerptTruncated=trimmed)
        )

    kept = {f.path for f in selected}
    rejected = [
        RejectedCandidate(
            path=path,
            score=round(score, 2),
            reason=(
                f"score {score:.1f} below cutoff {MIN_SCORE}" if score < MIN_SCORE else f"ranked below top {top_n}"
            ),
        )
        for score, path, _reasons in scored
        if path not in kept
    ][:TOP_N_REJECTED]

    return ContextSelection(selected=selected, rejected=rejected)
