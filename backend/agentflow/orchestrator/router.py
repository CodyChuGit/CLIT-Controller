"""Task A2 — typed wrapper over the engine's ``route()``.

Maps an AgentComposer task (its goal text and optional explicit task type) onto
an engine routing decision, returned as typed :class:`RouteResult` / :class:`Stage`
objects so the rest of the adapter never touches raw engine dicts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import _engine


@dataclass
class Stage:
    agent: str
    persona: str
    action: str
    parallel_group: Optional[str] = None


@dataclass
class RouteResult:
    decision: str
    primary_agent: str
    stages: list[Stage]
    monitor: bool
    confidence: float
    rationale: str
    task_type: Optional[str] = None


def _to_result(d: dict) -> RouteResult:
    stages = [
        Stage(
            agent=s.get("agent", ""),
            persona=s.get("persona", ""),
            action=s.get("action", ""),
            parallel_group=s.get("parallel_group"),
        )
        for s in (d.get("stages") or [])
    ]
    return RouteResult(
        decision=d.get("decision", ""),
        primary_agent=d.get("primary_agent", ""),
        stages=stages,
        monitor=bool(d.get("monitor")),
        confidence=float(d.get("confidence", 0.0)),
        rationale=d.get("rationale", ""),
        task_type=d.get("task_type"),
    )


def route_for_task(
    goal: str,
    *,
    task_type: Optional[str] = None,
    long_running: bool = False,
    large_logs: bool = False,
    task_id: Optional[str] = None,
) -> RouteResult:
    """Route by explicit ``task_type`` when known, else infer from ``goal`` text."""
    ns = _engine.load()
    decision = ns.route_task.route(
        task_type=task_type,
        text=goal or None,
        long_running=long_running,
        large_logs=large_logs,
        task_id=task_id,
    )
    return _to_result(decision)


def route_for_text(
    text: str,
    *,
    long_running: bool = False,
    large_logs: bool = False,
    task_id: Optional[str] = None,
) -> RouteResult:
    """Convenience: route purely from free text (no explicit task type)."""
    return route_for_task(
        text,
        long_running=long_running,
        large_logs=large_logs,
        task_id=task_id,
    )
