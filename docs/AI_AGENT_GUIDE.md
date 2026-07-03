# AI Agent Guide

Use this when a coding agent is working in this repository.

## Read First

1. [ARCHITECTURE.md](ARCHITECTURE.md)
2. [BACKEND.md](BACKEND.md)
3. [FRONTEND.md](FRONTEND.md)
4. [CONFIGURATION.md](CONFIGURATION.md)
5. [SECURITY.md](SECURITY.md)

For product behavior, read [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md) and
[FEATURE_STATUS.md](FEATURE_STATUS.md).

## Current Product Shape

CLIT Controller IDE is a local UI for CLI coding agents. It runs user-installed
provider CLIs as subprocesses, streams managed output through a shared event
store, and exposes interactive provider PTYs through Agent Dock.

Default roles:

| Role | Provider |
| --- | --- |
| Controller | `claude` |
| PM | `codex` |
| Engineer | `claude` |
| QA | `antigravity` |

Antigravity is not selectable as controller in the current UI. Old Gemini and
Antigravity-controller configs are migrated forward.

## Do Not Break These

- Controller mutations go through `CLITC_RESULT_V1`.
- Invalid controller result blocks mutate no state.
- Legacy `agentflow-*` directives are compatibility fallback only.
- Live managed output flows through `event_bus.py` and `stream.tsx`.
- Provider terminal tabs use `terminal_service.py` and `TerminalPane.tsx`.
- Frontend HTTP calls go through `frontend/src/api.ts`.
- Agent/user paths must stay inside the selected workspace.
- Subprocesses use argv lists, not `shell=True`.
- Secrets are redacted before persistence and broadcast.
- Headroom is fail-open.

## Controller Protocol

The backend validates the structured result block and then executes one action
from the closed action union:

- answer
- create_task
- queue_steps
- run_command
- request_approval
- request_user
- retry
- reroute
- complete_task
- cancel

Relevant code:

- `backend/agentflow/controller/engine.py`
- `backend/agentflow/controller/actions.py`
- `backend/agentflow/controller/context.py`
- `backend/agentflow/controller_protocol.py`
- `backend/agentflow/chat_service.py`

## Frontend Surfaces

- Agent Dock is the right-hand live control center.
- Provider tabs are real PTY terminals.
- Tasks shows provider-lane task distribution and detailed replay.
- Logs shows redacted global logs and active run tails.
- Preview starts and checks a localhost dev server.

Do not add a second terminal surface unless the app navigation is intentionally
changed.

## Verification

Run the smallest reliable check:

```bash
.venv/bin/python -m pytest backend/tests/test_controller_protocol.py
npm --prefix frontend run test -- src/pages/tasks/TaskDispatchMap.test.tsx
```

Use the full gate before broad handoff:

```bash
make verify
```

Docs-only changes should at least run stale-reference searches.
