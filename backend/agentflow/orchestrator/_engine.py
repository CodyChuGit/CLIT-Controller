"""Locate and import the pure-stdlib Agent_CLI_Skill orchestration engine once.

Resolution order for the engine ``scripts/`` dir:
  1. ``$AGENTCLI_CORE_PATH``
  2. ``/Users/cody/Agent_CLI_Skill/agent-orchestrator/scripts``  (dev default)
  3. ``<this package>/_engine_snapshot/scripts``                 (vendored, CI fallback)

``dispatch``, ``usage_lib``, ``monitor_lib`` and ``_lib`` are ordinary importable
module names; ``route-task.py`` is hyphenated, so it is loaded by file path and
registered under the name ``route_task``.

This is the single point of coupling between AgentComposer and the engine.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

_ENGINE: Optional[SimpleNamespace] = None

# ponytail: hard-coded dev path is the user's machine; env + vendored snapshot
# cover every other case. No config system for one path.
_DEV_DEFAULT = "/Users/cody/Agent_CLI_Skill/agent-orchestrator/scripts"


def _candidate_dirs() -> list[Path]:
    here = Path(__file__).resolve().parent
    raw = [
        os.environ.get("AGENTCLI_CORE_PATH"),
        _DEV_DEFAULT,
        str(here / "_engine_snapshot" / "scripts"),
    ]
    return [Path(c) for c in raw if c]


def _resolve_dir() -> Path:
    for d in _candidate_dirs():
        if (d / "dispatch.py").is_file() and (d / "route-task.py").is_file():
            return d
    raise RuntimeError(
        "Agent_CLI_Skill engine not found. Set AGENTCLI_CORE_PATH to its scripts/ "
        "dir, or run scripts/sync-engine.sh to vendor a snapshot. Looked in: "
        + ", ".join(str(d) for d in _candidate_dirs())
    )


def load() -> SimpleNamespace:
    """Import the engine once; return a namespace of its modules (cached)."""
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    scripts_dir = _resolve_dir()
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    # Ordinary importable modules (underscore / unqualified names live in scripts_dir).
    import _lib  # noqa: E402
    import dispatch  # noqa: E402
    import monitor_lib  # noqa: E402
    import usage_lib  # noqa: E402

    # route-task.py is hyphenated -> load by path, register as `route_task`.
    route_task = sys.modules.get("route_task")
    if route_task is None:
        spec = importlib.util.spec_from_file_location(
            "route_task", str(scripts_dir / "route-task.py")
        )
        if spec is None or spec.loader is None:  # pragma: no cover - defensive
            raise RuntimeError(f"cannot load route-task.py from {scripts_dir}")
        route_task = importlib.util.module_from_spec(spec)
        sys.modules["route_task"] = route_task
        spec.loader.exec_module(route_task)

    _ENGINE = SimpleNamespace(
        route_task=route_task,
        dispatch=dispatch,
        usage_lib=usage_lib,
        monitor_lib=monitor_lib,
        lib=_lib,
        scripts_dir=scripts_dir,
    )
    return _ENGINE
