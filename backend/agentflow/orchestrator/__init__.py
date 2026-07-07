"""Adapter rebasing AgentComposer's agent decisions onto the Agent_CLI_Skill engine.

The pure-stdlib orchestration core (``route-task.py`` / ``dispatch.py`` /
``usage_lib.py`` / ``monitor_lib.py``) is imported once via :mod:`._engine` and
consumed in ``cli_only`` mode. Public surface:

    from agentflow.orchestrator import router, dispatch_adapter, usage_bridge, caps

Modules are imported lazily by callers so importing this package never eagerly
loads the engine (which lives outside the repo in dev).
"""
