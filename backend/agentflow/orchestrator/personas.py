"""Task A5 — one parameterized persona-prompt builder for engine stages.

``route()`` returns stages carrying persona names from the orchestrator
vocabulary (``codebase-analyst``, ``qa-runner``, ``independent-reviewer``, …).
This builds a role-scoped prompt for any such persona from ``config/personas.yaml``,
in AgentComposer's house style (usage header + task folder + ponytail block).
Legacy step ids map to their nearest persona for backward compatibility; unknown
personas get a generic fallback.

``ctx`` keys (all optional): ``usage_header`` (pre-built budget string),
``task_rel_dir``, ``message``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from agentflow import ponytail

from . import _engine

# Legacy AgentComposer step id -> engine (or local) persona.
LEGACY_STEP_PERSONA = {
    "codex_spec": "spec-writer",
    "claude_implement": "implementer",
    "gemini_qa": "qa-runner",
    "codex_review": "independent-reviewer",
    "claude_fix": "implementer",
}

# Roles AgentComposer needs that the engine doesn't define (Claude-owned work).
_LOCAL_PERSONAS: dict[str, dict] = {
    "spec-writer": {
        "purpose": "Write a compact, specific spec and implementation plan; do not edit production code.",
        "quality_standards": ["compact and specific", "optimizes for minimal Claude implementation time"],
        "failure_conditions": ["edits production code", "padded or vague plan"],
        "required_outputs": ["a spec and an implementation plan in the task folder"],
    },
    "implementer": {
        "purpose": "Implement only the requested production changes; keep the diff minimal and focused.",
        "quality_standards": ["implements only what was requested", "no unrelated refactors"],
        "failure_conditions": ["refactors unrelated files", "adds tests unless asked"],
        "required_outputs": ["the production change and a short implementation summary"],
    },
}


@lru_cache(maxsize=1)
def _engine_personas() -> dict:
    """name -> persona dict, merged from personas.yaml (codex + antigravity groups)."""
    ns = _engine.load()
    path = ns.scripts_dir.parent / "config" / "personas.yaml"
    data = ns.lib.read_yaml(str(path)) if path.is_file() else {}
    out: dict = {}
    for group in ("codex_personas", "antigravity_personas"):
        for p in data.get(group) or []:
            if p.get("name"):
                out[p["name"]] = p
    return out


def _definition(persona: str) -> Optional[dict]:
    return _LOCAL_PERSONAS.get(persona) or _engine_personas().get(persona)


def _as_text(x) -> str:
    # The minimal YAML reader can parse "a: b" scalars (e.g. "file:line") into a
    # dict, so coerce every item to a string defensively.
    if isinstance(x, dict):
        return "; ".join(f"{k}: {v}" for k, v in x.items())
    return str(x)


def _bullets(items) -> str:
    return "\n".join(f"- {_as_text(x)}" for x in (items or []))


def persona_prompt(persona: str, ctx: dict) -> str:
    """Build a role-scoped prompt for a persona from ctx."""
    parts: list[str] = []
    if ctx.get("usage_header"):
        parts.append(ctx["usage_header"])
    if ctx.get("task_rel_dir"):
        parts.append(f"Task folder: {ctx['task_rel_dir']}/")

    message = ctx.get("message", "")
    d = _definition(persona)
    if d is None:
        body = (
            f"You are the `{persona}` for this task. Do the work that role implies, "
            "grounded in the workspace. Be concrete and minimal."
        )
        if message:
            body += f"\n\n{message}"
    else:
        chunks = [f"You are the `{persona}`.", d.get("purpose", "")]
        if message:
            chunks.append(message)
        if d.get("quality_standards"):
            chunks.append("Standards:\n" + _bullets(d["quality_standards"]))
        if d.get("required_outputs"):
            chunks.append("Produce: " + "; ".join(_as_text(x) for x in d["required_outputs"]))
        if d.get("failure_conditions"):
            chunks.append("Avoid:\n" + _bullets(d["failure_conditions"]))
        body = "\n\n".join(c for c in chunks if c)

    parts.append(body)
    prompt = "\n\n".join(parts)
    pony = ponytail.block()
    opensrc = (
        "Reading dependency source: run `opensrc path <pkg>` to fetch + cache any open-source "
        "package's real source and get a local path (e.g. `opensrc path zod`, "
        "`opensrc path pypi:requests`, `opensrc path owner/repo`), then read files under it."
    )
    return prompt + (f"\n\n{pony}" if pony else "") + f"\n\n{opensrc}"
