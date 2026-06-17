"""Workflow step definitions and handoff contract."""

from __future__ import annotations

# step id -> (routing role, human label)
STEP_DEFS: dict[str, dict[str, str]] = {
    # Labels are provider-neutral; the routed provider is shown alongside in the UI.
    "codex_spec": {"role": "pm", "label": "Write Spec"},
    "claude_implement": {"role": "engineer", "label": "Implement"},
    "gemini_qa": {"role": "qa", "label": "QA / Test"},
    "codex_review": {"role": "pm", "label": "Final Review"},
    "claude_fix": {"role": "engineer", "label": "Fix Bugs"},
}

# What each step reads and writes; "@diff", "@code", and "@folder" are virtual
# inputs/outputs shown in the UI rather than literal files.
STEP_IO: dict[str, dict[str, list[str]]] = {
    "codex_spec": {
        "reads": ["00_USER_GOAL.md"],
        "writes": ["01_CODEX_SPEC.md", "02_CODEX_IMPLEMENTATION_PLAN.md"],
    },
    "claude_implement": {
        "reads": ["01_CODEX_SPEC.md", "02_CODEX_IMPLEMENTATION_PLAN.md"],
        "writes": ["@code", "04_CLAUDE_IMPLEMENTATION_SUMMARY.md"],
    },
    "gemini_qa": {
        "reads": ["@diff", "04_CLAUDE_IMPLEMENTATION_SUMMARY.md"],
        "writes": ["05_QA_RESULTS.md", "06_BUGS_FOR_CLAUDE.md"],
    },
    "codex_review": {
        "reads": ["@diff", "@folder"],
        "writes": ["07_CODEX_FINAL_REVIEW.md"],
    },
    "claude_fix": {
        "reads": ["06_BUGS_FOR_CLAUDE.md"],
        "writes": ["@code", "04_CLAUDE_IMPLEMENTATION_SUMMARY.md"],
    },
}

FULL_SEQUENCE = ["codex_spec", "claude_implement", "gemini_qa", "codex_review"]
