"""Build the capability dict the engine's dispatch/usage layer expects.

Keys read by the engine (``dispatch.py`` / ``usage_lib.py``):
    ``codex_cli``, ``codex_plugin``, ``agy_cli``, ``agy_plugin``, ``omlx``.

AgentComposer spawns CLIs directly (``cli_only`` dispatch mode) and never uses
Claude-Code plugins, so ``*_plugin`` are always ``False``.
"""

from __future__ import annotations

from agentflow import provider_probe


def build_caps() -> dict:
    """Map installed-CLI detection onto the engine's capability keys."""
    return {
        "codex_cli": provider_probe.which("codex") is not None,
        "codex_plugin": False,
        # provider id "antigravity" resolves the `agy` (or `antigravity`) binary.
        "agy_cli": provider_probe.which("antigravity") is not None,
        "agy_plugin": False,
        "omlx": provider_probe.which("omlx") is not None,
    }


def installed_agents() -> dict:
    """Agent-name-keyed install map for usage_lib.resolve() (codex/antigravity/omlx).

    Distinct from build_caps(): resolve() keys by agent name, dispatch by *_cli.
    """
    return {
        "codex": provider_probe.which("codex") is not None,
        "antigravity": provider_probe.which("antigravity") is not None,
        "omlx": provider_probe.which("omlx") is not None,
    }
