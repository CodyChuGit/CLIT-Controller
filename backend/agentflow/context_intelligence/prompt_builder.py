"""Prompt package builder: renders a ContextPackage in a stable section order.

The order below is a contract — ``test_context_prompt_builder`` locks it.
Stable text lives here (NOT in ``prompt_templates.py``: live prompt paths are
untouched in Phase 1).
"""

from __future__ import annotations

from .types import ContextPackage, PromptPackage, PromptSection

SECTION_ORDER: tuple[str, ...] = (
    "system_instructions",
    "clitc_rules",
    "behavior_policy",
    "project_rules",
    "session_digest",
    "repo_map",
    "selected_files",
    "git_diff",
    "log_context",
    "user_task",
)

_SYSTEM_INSTRUCTIONS = (
    "You are an engineering agent working inside the user's selected workspace. "
    "Ground every answer in the context sections below; do not invent files or state."
)

_CLITC_RULES = (
    "CLITC rules: stay inside the workspace, never read or write .env files, "
    "never print secrets, and prefer the smallest correct change."
)

_MAP_LINES = 60


def _repo_map_text(package: ContextPackage) -> str:
    entries = package.repoMap.entries[:_MAP_LINES]
    if not entries:
        return ""
    lines = [
        f"{e.path} ({e.language or 'text'}, {e.size}B)" + (f" — {', '.join(e.symbols[:6])}" if e.symbols else "")
        for e in entries
    ]
    if package.repoMap.truncated or len(package.repoMap.entries) > _MAP_LINES:
        lines.append("[… repo map truncated]")
    return "Repo map:\n" + "\n".join(lines)


def _selected_files_text(package: ContextPackage) -> str:
    parts: list[str] = []
    for f in package.selection.selected:
        header = f"### {f.path} (score {f.score}; {'; '.join(f.reasons)})"
        parts.append(f"{header}\n{f.excerpt}".rstrip())
    return "\n\n".join(parts)


def _git_text(package: ContextPackage) -> str:
    if not package.git.isRepo or not package.git.changedFiles:
        return ""
    header = f"Git branch {package.git.branch}; changed: {', '.join(package.git.changedFiles)}"
    return f"{header}\n{package.git.diff}".rstrip()


def build_prompt_package(package: ContextPackage) -> PromptPackage:
    """Render every section in SECTION_ORDER; empty sections are kept (with empty
    content) so the order is observable and testable end to end."""
    content: dict[str, str] = {
        "system_instructions": _SYSTEM_INSTRUCTIONS,
        "clitc_rules": _CLITC_RULES,
        "behavior_policy": package.policy.block,
        "project_rules": package.projectRules,
        "session_digest": package.digest.text,
        "repo_map": _repo_map_text(package),
        "selected_files": _selected_files_text(package),
        "git_diff": _git_text(package),
        "log_context": package.logs.summary,
        "user_task": f"USER TASK:\n{package.task.text}",
    }
    sections = [PromptSection(name=name, content=content[name]) for name in SECTION_ORDER]
    text = "\n\n".join(f"## {s.name}\n{s.content}" for s in sections if s.content)
    return PromptPackage(sections=sections, text=text)
