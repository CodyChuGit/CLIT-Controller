# Development

This is the local contributor workflow for CLIT Controller IDE.

## Setup

```bash
make setup
```

This creates `.venv`, installs the backend package with dev dependencies, and
installs frontend dependencies.

## Run

```bash
make dev
```

Development URLs:

- frontend: `http://localhost:5180`
- backend: `http://localhost:8787`
- API docs: `http://localhost:8787/docs`

The frontend dev server proxies `/api`, SSE, and terminal WebSockets to the
backend.

## Build

```bash
make build
AGENTFLOW_PORT=8787 .venv/bin/python -m agentflow
```

The backend serves `frontend/dist` on `http://localhost:8787`.

## Common Workflows

### Backend Route

1. Add or update the route in `backend/agentflow/api/`.
2. Keep the handler thin.
3. Put behavior in a service module.
4. Add or update tests in `backend/tests/`.
5. Update [API.md](API.md) and [BACKEND.md](BACKEND.md).

### Controller Action

1. Update the protocol parser or models only when the action contract changes.
2. Update `backend/agentflow/controller/actions.py`.
3. Keep policy and approvals in the execution path for commands.
4. Test invalid output, valid output, and no-mutation behavior.
5. Update [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md), [BACKEND.md](BACKEND.md),
   and [FEATURE_STATUS.md](FEATURE_STATUS.md).

### Frontend API Workflow

1. Add the API wrapper in `frontend/src/api.ts`.
2. Add types in `frontend/src/types.ts` if needed.
3. Render live output through `stream.tsx` when it is run/event data.
4. Add targeted Vitest or Testing Library coverage.
5. Update [FRONTEND.md](FRONTEND.md) and [API.md](API.md).

### Task Or Dock UI

1. Reuse Agent Dock, `TerminalPane`, `TimelineCard`, `RawDetail`, and
   display-model helpers where possible.
2. Keep structured summaries above raw logs.
3. Preserve disconnected, missing-provider, approval, blocked, failed, and
   running states.
4. Test the changed model/helper or component.

## Checks

```bash
make format-check
make lint
make typecheck
make test
make build
make verify
```

Targeted examples:

```bash
.venv/bin/python -m pytest backend/tests/test_controller_protocol.py
.venv/bin/python -m pytest backend/tests/test_routes_terminals.py
npm --prefix frontend run test -- src/lib/liveActivity.test.ts
npm --prefix frontend run test -- src/pages/tasks/TaskDispatchMap.test.tsx
```

## Documentation Maintenance

Keep these docs aligned with code changes:

| Change | Docs |
| --- | --- |
| API route | [API.md](API.md), [BACKEND.md](BACKEND.md) |
| Controller behavior | [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md), [BACKEND.md](BACKEND.md), [FEATURE_STATUS.md](FEATURE_STATUS.md) |
| Event stream or run state | [ARCHITECTURE.md](ARCHITECTURE.md), [DATA_MODEL.md](DATA_MODEL.md), [FRONTEND.md](FRONTEND.md) |
| Terminal behavior | [API.md](API.md), [BACKEND.md](BACKEND.md), [FRONTEND.md](FRONTEND.md), [TROUBLESHOOTING.md](TROUBLESHOOTING.md) |
| Routing, templates, models, Headroom, Ponytail | [CONFIGURATION.md](CONFIGURATION.md) |
| State files | [DATA_MODEL.md](DATA_MODEL.md) |
| Security or policy | [SECURITY.md](SECURITY.md), [adr/0001-auto-run-policy-allowlist.md](adr/0001-auto-run-policy-allowlist.md) |
| UI structure | [FRONTEND.md](FRONTEND.md), [DESIGN.md](../DESIGN.md) |

Delete stale planning docs instead of letting them conflict with current
reference docs.
