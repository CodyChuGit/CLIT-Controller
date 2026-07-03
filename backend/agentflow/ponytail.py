"""Ponytail — prompt-level minimalism, the output-side token strategy.

Headroom compresses what goes INTO the model (see headroom_service); Ponytail
(github.com/DietrichGebert/ponytail) shrinks what comes OUT: every agent step
prompt carries a compact "lazy senior dev" instruction block — the decision
ladder (YAGNI → reuse → stdlib → native → installed dep → one line → minimum
code) — so agents write less code, shorter plans, and terser replies. Its
published benchmark: ~54% less code, ~22% fewer tokens, same safety compliance.

Levels mirror upstream: off | lite | full (default) | ultra. The level lives in
global config (``ponytail.level``) and is editable from Settings.
"""

from __future__ import annotations

from . import config

LEVELS = ("off", "lite", "full", "ultra")
DEFAULT_LEVEL = "full"

_LADDER = (
    "Ponytail discipline — the lazy senior dev. Before writing anything, climb this "
    "ladder and stop at the first rung that holds: "
    "1) does this need to exist at all? (YAGNI) "
    "2) already in this codebase? reuse it. "
    "3) stdlib does it? use it. "
    "4) native platform feature covers it? "
    "5) an already-installed dependency solves it? never add a new one for a few lines. "
    "6) can it be one line? "
    "7) only then: the minimum code that works."
)

_RULES = (
    "No unrequested abstractions, no scaffolding for later, fewest files, shortest "
    "working diff. Mark deliberate shortcuts with a `ponytail:` comment naming the "
    "ceiling and upgrade path. Never simplify away input validation, error handling "
    "that prevents data loss, security, or accessibility."
)

_BLOCKS = {
    "lite": _LADDER,
    "full": f"{_LADDER} {_RULES} Keep prose to a few lines: what you did, what you skipped, when to add it.",
    "ultra": (
        f"{_LADDER} {_RULES} ULTRA: be ruthless — prefer deleting code over adding it, "
        "question every requested layer, one-line answers where they suffice, and cap "
        "any explanation at three short lines."
    ),
}


def level() -> str:
    raw = str((config.load_global_config().get("ponytail") or {}).get("level", DEFAULT_LEVEL))
    return raw if raw in LEVELS else DEFAULT_LEVEL


def block(lvl: str | None = None) -> str:
    """The instruction block injected into agent prompts ('' when off)."""
    return _BLOCKS.get(lvl if lvl is not None else level(), "")
