"""Budget-aware routing recommendations and ROUTING_DECISIONS.md writing."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import paths
from .usage_service import provider_health

MODE_LABELS = {
    "maximum_quality": "Maximum Quality",
    "balanced": "Balanced",
    "budget_saver": "Budget Saver",
    "manual_approval": "Manual Approval",
}

HEALTH_NOTES = {"green": "safe", "yellow": "conserve", "red": "avoid"}

# Goals shorter than this are "small tasks" for Budget Saver spec-skipping.
SMALL_TASK_GOAL_CHARS = 280


def budget_context_header(usage: dict) -> str:
    mode = usage.get("orchestrationMode", "balanced")
    return (
        "Budget context:\n"
        f"- Current mode: {MODE_LABELS.get(mode, mode)}\n"
        f"- Claude usage: {provider_health(usage, 'claude')}\n"
        f"- Antigravity usage: {provider_health(usage, 'antigravity')}\n"
        f"- Codex usage: {provider_health(usage, 'codex')}\n"
        "- Instruction: minimize full-file context, prefer diffs, file paths, and task markdown.\n"
        "- Do not call expensive agents unless required."
    )


def recommend(usage: dict, task_type: str = "feature", diff_size: int | None = None) -> dict:
    """Apply the routing rules to current usage state."""
    mode = usage.get("orchestrationMode", "balanced")
    claude = provider_health(usage, "claude")
    antigravity = provider_health(usage, "antigravity")
    codex = provider_health(usage, "codex")

    lines: list[str] = []
    warnings: list[str] = []
    selected = "claude"
    cheaper = False

    if claude == "red":
        cheaper = True
        selected = "codex"
        warnings.append("Claude is RED — avoid Claude unless production code changes are strictly required.")
        lines += [
            "Avoid Claude unless production code changes are required.",
            "Write the spec and plan with Codex first.",
            "Use Antigravity for QA and broad checks.",
            "Run local tests and git checks before any Claude call.",
        ]
    elif claude == "yellow":
        cheaper = True
        lines += [
            "Claude allowed for implementation only — not for planning or review.",
            "Keep Claude prompts small: send the plan and diffs, never whole files.",
            "Use Codex for planning/review and Antigravity for QA.",
        ]
    else:
        lines.append("Claude is green — standard chain: Codex spec → Claude implement → Antigravity QA → Codex review.")

    if antigravity == "green":
        lines.append("Antigravity is green — prefer Antigravity for orchestration and QA.")
    elif antigravity == "red":
        warnings.append("Antigravity is RED — route QA to Codex or run local checks only.")

    if codex == "red":
        warnings.append("Codex is RED — skip spec/review steps or draft specs manually.")

    if mode == "budget_saver":
        cheaper = True
        lines += [
            "Budget Saver: skip the Codex spec for small tasks and send a compact prompt straight to the engineer.",
            "Run local git/test commands first.",
            "Prefer diffs and file paths over whole files.",
        ]
    elif mode == "maximum_quality":
        lines.append("Maximum Quality: run the full chain including Codex final review.")
    elif mode == "manual_approval":
        lines.append("Manual Approval: no agent command runs automatically — review each command preview, then run it.")

    if diff_size is not None and diff_size > 20_000:
        lines.append("Large diff detected — send `git diff --stat` plus only the relevant file paths, not the full diff.")

    return {
        "mode": mode,
        "modeLabel": MODE_LABELS.get(mode, mode),
        "budgetContext": budget_context_header(usage),
        "lines": lines,
        "warnings": warnings,
        "selectedProvider": selected,
        "manualApprovalRecommended": mode == "manual_approval" or claude == "red",
        "cheaperRouteRecommended": cheaper,
        "health": {"claude": claude, "antigravity": antigravity, "codex": codex},
    }


def _decision_block(usage: dict, routing: dict, task_title: str) -> str:
    rec = recommend(usage)
    claude, antigravity, codex = rec["health"]["claude"], rec["health"]["antigravity"], rec["health"]["codex"]
    if claude == "red":
        decision = (
            f"Use {routing['pm']} for spec and plan, run local checks, use {routing['qa']} for QA. "
            "Only call Claude if production code changes are unavoidable."
        )
    else:
        decision = (
            f"Use {routing['pm']} for spec, {routing['engineer']} for implementation, "
            f"{routing['qa']} for QA, {routing['pm']} for final review."
        )
    return (
        "# Routing Decisions\n\n"
        "## Task\n"
        f"{task_title}\n\n"
        "## Budget Context\n"
        f"- Mode: {rec['modeLabel']}\n"
        f"- Claude: {claude} / {HEALTH_NOTES[claude]}\n"
        f"- Codex: {codex} / {HEALTH_NOTES[codex]}\n"
        f"- Antigravity: {antigravity} / {HEALTH_NOTES[antigravity]}\n\n"
        "## Decision\n"
        f"{decision}\n\n"
        "## Usage Saving Strategy\n"
        "- Send task files and git diff instead of full repo.\n"
        "- Claude receives implementation plan only.\n"
        "- Antigravity handles QA instead of Claude.\n"
    )


def write_initial_decisions(workspace: Path, task_id: str, task_title: str, usage: dict, routing: dict) -> None:
    path = paths.task_dir(workspace, task_id) / "ROUTING_DECISIONS.md"
    path.write_text(_decision_block(usage, routing, task_title), encoding="utf-8")


def append_decision(workspace: Path, task_id: str, text: str) -> None:
    path = paths.task_dir(workspace, task_id) / "ROUTING_DECISIONS.md"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entry = f"\n## Update — {stamp}\n{text.strip()}\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
