# Repository Structure

This is the current source map for CLIT Controller IDE / AgentComposer.

```text
AgentComposer/
├── backend/
│   ├── agentflow/
│   │   ├── api/                 # FastAPI HTTP, SSE, and WebSocket routes
│   │   ├── controller/          # CLITC_RESULT_V1 action engine
│   │   └── *.py                 # services, state, runner, terminals, config
│   └── tests/                   # pytest suite
├── frontend/
│   ├── public/                  # manifest, service worker, icons
│   └── src/
│       ├── components/          # shared UI, dock, terminals, conversation views
│       ├── lib/                 # pure helpers and display/event models
│       ├── pages/               # top-level app pages
│       ├── App.tsx              # app shell
│       ├── api.ts               # only normal HTTP client
│       └── stream.tsx           # SSE/polling event store
├── scripts/                     # setup, dev, app packaging, Headroom helper
├── docs/                        # current reference documentation
├── Makefile                     # setup/dev/check command surface
├── pyproject.toml               # backend package and Python tooling
├── requirements.lock            # pinned Python dependencies
├── README.md
├── DESIGN.md
├── CONTRIBUTING.md
└── CHANGELOG.md
```

The Python package is still named `agentflow`; the product name is CLIT
Controller IDE.

## Backend

Important modules:

| Path | Purpose |
| --- | --- |
| `backend/agentflow/app.py` | FastAPI app factory, middleware, router registration, lifespan. |
| `backend/agentflow/config.py` | Global and workspace config, migrations, routing defaults. |
| `backend/agentflow/controller/` | Structured controller action context, engine, and executors. |
| `backend/agentflow/process_runner.py` | Managed subprocess execution and live output events. |
| `backend/agentflow/terminal_service.py` | PTY sessions for provider terminal tabs. |
| `backend/agentflow/task_service.py` | Task folders, step runs, artifacts, exchanges. |
| `backend/agentflow/queue_service.py` | Durable queue and dispatcher loop. |
| `backend/agentflow/chat_service.py` | Controller and direct provider chat. |
| `backend/agentflow/state_store.py` | Durable events, runs, approvals, and recovery. |
| `backend/agentflow/event_bus.py` | Workspace live event stream. |
| `backend/agentflow/policy_service.py` | Command allow / approval / deny decisions. |
| `backend/agentflow/provider_probe.py` | Provider definitions, executable resolution, installs, logins. |
| `backend/agentflow/headroom_service.py` | Managed fail-open Headroom proxy integration. |

Routers live in `backend/agentflow/api/` and should stay thin. Business logic
belongs in services.

## Frontend

Current top-level pages:

- `projects`
- `agents`
- `tasks`
- `preview`
- `usage`
- `logs`
- `settings`

There is no standalone Terminals page. Provider terminals live inside Agent Dock.

Important frontend areas:

| Path | Purpose |
| --- | --- |
| `frontend/src/App.tsx` | Shell, page routing, Agent Dock, event provider. |
| `frontend/src/api.ts` | Typed wrappers for backend endpoints. |
| `frontend/src/stream.tsx` | SSE store, polling fallback, per-run stream accumulation. |
| `frontend/src/components/dock/` | Agent Dock frame, tabs, transcript, composer, live run, terminal drawer. |
| `frontend/src/components/TerminalPane.tsx` | xterm.js PTY WebSocket client. |
| `frontend/src/pages/TasksPage.tsx` | Task workbench shell. |
| `frontend/src/pages/tasks/TaskDispatchMap.tsx` | Provider-lane task distribution map. |
| `frontend/src/lib/displayModel.ts` | Shared event-to-card presentation model. |
| `frontend/src/lib/liveActivity.ts` | Live activity derivation for dock/tasks. |

## Docs

Only current reference docs should stay in `docs/`. Stale planning notes have
been removed from the maintained documentation set.

Start at [INDEX.md](INDEX.md).
