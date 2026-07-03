# Architecture

CLIT Controller IDE is a single-user local app:

- FastAPI backend in `backend/agentflow`
- React/Vite frontend in `frontend/src`
- user-installed CLI agents as subprocesses
- JSON state in `~/.agentflow/` and `<workspace>/.agentflow/`
- live output over SSE and PTY WebSockets

## Runtime Layout

```text
Browser / app window
  ActivityBar + pages + AgentDock
        |
        | HTTP / SSE / WebSocket
        v
FastAPI backend on localhost:8787
  projects  agents  chat  tasks  queue  logs  usage  preview  terminals  state
        |
        | subprocess / PTY / filesystem
        v
Selected workspace + user CLIs
  codex  claude  agy  git  gh  shell commands  preview server
```

During development, Vite runs on `:5180` and proxies `/api` and WebSockets to
the backend on `:8787`. A production build can be served by the backend on the
same port.

## Frontend Shape

`App.tsx` mounts:

- `ActivityBar`: Explorer, Agents, Tasks, Preview, Usage, Logs, Settings.
- `EventStreamProvider`: the single workspace event subscription.
- page content inside an `ErrorBoundary`.
- right-hand `AgentDock`.
- bottom `StatusBar`.

The Agent Dock is the live control center. The controller tab renders chat,
activity cards, approvals, live run output, composer, and terminal drawer. The
provider tabs render real PTY terminals.

The Tasks page renders a provider-lane dispatch map plus detailed step cards,
queue controls, continuation input, command cards, changed files, artifacts, and
paginated raw detail.

## Backend Shape

Key services:

| Module | Responsibility |
| --- | --- |
| `app.py` | FastAPI app, route registration, lifespan, startup recovery, terminal sweep, dispatcher lifecycle. |
| `config.py` | Global/workspace config, default routing, command templates, migrations. |
| `chat_service.py` | Chat persistence, CLI launch facade, pending state, direct/provider chat. |
| `controller/engine.py` | Parses finished controller output and applies the controller decision. |
| `controller/actions.py` | Executes validated `ControllerAction` values through task, queue, policy, approval, and runner services. |
| `controller/context.py` | Workspace and focused-task prompt context builders. |
| `controller_protocol.py` | `CLITC_RESULT_V1` schema and parser. |
| `process_runner.py` | Subprocess lifecycle, stdout/stderr capture, cancellation, redacted logs, live event deltas. |
| `event_bus.py` | In-process event ring buffer for SSE/polling live stream. |
| `state_store.py` | Durable events, runs, approvals, and restart recovery. |
| `task_service.py` | Task folders, markdown handoff files, step prompts, run completion, task detail. |
| `queue_service.py` | Durable queue and dispatcher. |
| `terminal_service.py` | PTY sessions, scrollback, metadata frames, orphan cleanup. |
| `provider_probe.py` | Provider definitions, detection, install/login/model helpers. |
| `policy_service.py` | Allow / require approval / deny command classification. |
| `headroom_service.py` | In-process, fail-open Headroom context compression (no proxy). |
| `ponytail.py` | Prompt-level output discipline block. |

## Controller Flow

```text
InputSubmission or /chat/send
  -> chat_service starts the controller CLI
  -> process_runner streams controller.delta events
  -> controller output completes
  -> controller_protocol parses CLITC_RESULT_V1
  -> controller.engine applies result
  -> controller.actions mutates task/queue/approval/run state
  -> state_store and event_bus publish durable/live events
```

Invalid `CLITC_RESULT_V1` blocks produce `controller.result_invalid` and do not
mutate state. If no result block exists, legacy directives are mapped onto the
same closed action union as a compatibility fallback and emit
`controller.legacy_directives`.

## Streaming Model

Managed runs stream through one event path:

- SSE: `GET /api/events/stream`
- fallback: `GET /api/events?cursor=<id>`

Events include:

- `controller.delta`
- `chat.delta`
- `run.output`
- `run.stderr`
- `command.started`
- `command.finished`
- `queue.*`
- `approval.*`
- `task.*`
- `controller.turn_completed`

The frontend `streamStore` dedupes by event id, resumes by cursor, accumulates
per-run text, and exposes hooks such as `useRunStream`.

Interactive terminals are separate PTY sessions over:

- `WS /api/terminals/{provider}/ws`
- `GET /api/terminals/{provider}/diagnostics`

PTY byte frames stay binary for xterm. Metadata frames are JSON text and report
`launching`, `ready`, and `closed` lifecycle states.

## State And Recovery

Global state lives in `~/.agentflow/`; workspace state lives in
`<workspace>/.agentflow/`. JSON writes are atomic.

On startup and workspace selection, recovery settles:

- running records whose process is gone
- queue items stuck running
- task steps stuck running

On startup, terminal pidfiles under `~/.agentflow/run/terminals/` are swept so
orphaned PTY process groups do not accumulate.

## Security Boundaries

- localhost-only server
- CSRF/origin guard for mutating HTTP requests
- WebSocket origin check for terminal sockets
- no `shell=True` subprocesses
- workspace path confinement
- redaction before persistence/broadcast
- policy/approval gates for risky commands
- no provider credential custody
