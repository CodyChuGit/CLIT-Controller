# Backend Reference

The backend is a FastAPI app that owns the local trust boundary: workspace
selection, provider CLI execution, controller actions, queue dispatch, policy,
approvals, redaction, state recovery, live events, and PTY terminals.

## Entry Points

- `python -m agentflow` starts uvicorn.
- `agentflow.app:create_app()` builds the FastAPI app.
- `app.py` registers routes and runs lifespan startup/shutdown work.

Startup does three things:

1. recover any selected workspace state
2. sweep orphaned PTY terminal sessions
3. start Headroom management and the queue dispatcher

Shutdown cancels active managed runs and terminates PTY sessions.

## Routes

| Router | Prefix | Purpose |
| --- | --- | --- |
| `routes_projects.py` | `/api/projects` | workspace, files, git, settings |
| `routes_agents.py` | `/api/agents` | provider list/check/install/login/model |
| `routes_chat.py` | `/api/chat` | controller chat, direct chat, typed input submit, stop, clear |
| `routes_tasks.py` | `/api/tasks` | task CRUD, run steps, full sequence, logs, files, stop |
| `routes_queue.py` | `/api/queue` | queue state and operations |
| `routes_state.py` | `/api` | events, SSE stream, run lookup, approvals |
| `routes_logs.py` | `/api/logs` | redacted logs and active runs |
| `routes_usage.py` | `/api/usage` | usage counters, live usage, routing recommendations |
| `routes_preview.py` | `/api/preview` | localhost preview server |
| `routes_terminals.py` | `/api/terminals` | PTY diagnostics, kill, WebSocket |

## Controller Engine

The controller is a CLI run, not a hosted API call. `chat_service.py` starts the
provider CLI and persists chat messages; the `controller` package owns action
application after a controller run finishes.

Flow:

```text
chat_service.send / orchestrator_consult
  -> RUNNER.start(... stream_kind="controller")
  -> controller.delta events while stdout arrives
  -> controller.engine.apply_controller_output(...)
  -> controller_protocol.parse_controller_result(...)
  -> controller.actions.execute(...)
```

`CLITC_RESULT_V1` is primary. A valid block drives one validated action. An
invalid block creates a typed failure event and mutates nothing. If no block is
present, legacy `agentflow-*` directive blocks are mapped to the same action
union as a compatibility fallback and logged as `controller.legacy_directives`.

Supported actions:

- `answer`
- `create_task`
- `queue_steps`
- `run_command`
- `request_approval`
- `request_user`
- `retry`
- `reroute`
- `complete_task`
- `cancel`

Command actions still go through `policy_service` and durable approvals.

## Task And Queue Services

`task_service.py` owns:

- task ids and task folders
- markdown handoff files
- step previews and prompts
- step run lifecycle
- artifact and changed-file snapshots
- task detail responses
- step exchange reconstruction from logs

`queue_service.py` owns:

- `queue.json`
- one active item per provider
- intra-task ordering
- retry, skip, reroute, remove, clear
- blocked and approval states
- closed-loop controller consult after orchestrated steps

## Process Runner

`process_runner.py` starts child processes with argv lists and no shell
interpolation. It captures stdout/stderr incrementally, redacts output, writes
logs, publishes live deltas, tracks runtime state, and cancels process groups.

Streaming kinds:

- `controller` -> `controller.delta`
- `chat` -> `chat.delta`
- `run` -> `run.output` / `run.stderr`
- `command` -> `command.started` / `run.output` / `command.finished`

Headroom env injection happens here for supported providers when the proxy is
enabled and reachable.

## Event Bus And State Store

`event_bus.py` is the in-process live stream. Every event has a monotonic id and
can be read through SSE or polling.

`state_store.py` persists durable events, run records, and approvals. It also
mirrors structural events into the live bus.

High-frequency text deltas live in the event bus and full run logs; durable
structural state lives in JSON ledgers.

## Terminals

`terminal_service.py` owns real PTY sessions per `(workspace, provider)`.

Features:

- xterm-compatible raw byte stream
- scrollback replay on reconnect
- JSON metadata frames for lifecycle state
- diagnostics endpoint
- restart/kill endpoint
- orphan pidfile sweep on backend startup

Antigravity launches as a bare TUI and does not receive a starter prompt.

## Provider Probing

`provider_probe.py` defines providers, executable names, install commands, login
commands, model options, and version/model probes.

Agent provider ids are:

- `codex`
- `claude`
- `antigravity`

Optional providers such as Ollama and MLX are detected for local use but
are not queue/chat/task providers.

## Token Controls

`headroom_service.py` starts a managed Headroom proxy when enabled and installed.
It is fail-open and only routes `claude` and `codex`.

`ponytail.py` injects output-discipline instructions into agent prompts with
levels `off`, `lite`, `full`, and `ultra`.

## Backend Tests

Run targeted tests:

```bash
.venv/bin/python -m pytest backend/tests/test_controller_protocol.py
.venv/bin/python -m pytest backend/tests/test_chat_service.py
.venv/bin/python -m pytest backend/tests/test_streaming.py
.venv/bin/python -m pytest backend/tests/test_terminal_service.py backend/tests/test_routes_terminals.py
```

Run all backend tests:

```bash
make test-backend
```
