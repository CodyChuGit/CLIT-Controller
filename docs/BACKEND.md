# Backend

The Python backend is a single FastAPI process that orchestrates CLI coding agents
(`claude`, `codex`, `agy`/antigravity) as subprocesses, runs PTY terminals over
WebSockets, manages a per-workspace git workspace, and streams live agent output. It
is local-first and single-user: it binds loopback only and has **no authentication by
design** (see [SECURITY.md](SECURITY.md)).

This document describes the backend as it is actually implemented. For the product
shape see [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md) and [PILLARS.md](PILLARS.md); for
the system-wide view see [ARCHITECTURE.md](ARCHITECTURE.md); for running and operating
it see [OPERATIONS.md](OPERATIONS.md) and [DEVELOPMENT.md](DEVELOPMENT.md); for the
conventions every change follows see [ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md).
Known gaps are tracked in [LIMITATIONS.md](LIMITATIONS.md).

All code lives in [backend/agentflow/](../backend/agentflow); tests in
[backend/tests/](../backend/tests).

## Contents

1. [Entry point and app factory](#1-entry-point-and-app-factory)
2. [Lifespan: startup recovery, terminal sweep, shutdown](#2-lifespan-startup-recovery-terminal-sweep-shutdown)
3. [Middleware: CORS and the OriginGuard CSRF check](#3-middleware-cors-and-the-originguard-csrf-check)
4. [Route organization](#4-route-organization)
5. [Service layer](#5-service-layer)
6. [Domain: state machine, policy, routing](#6-domain-state-machine-policy-routing)
7. [Persistence: JSON ledgers and atomic writes](#7-persistence-json-ledgers-and-atomic-writes)
8. [Schemas: request models and output contracts](#8-schemas-request-models-and-output-contracts)
9. [The subprocess runner](#9-the-subprocess-runner)
10. [PTY terminals](#10-pty-terminals)
11. [The background dispatcher](#11-the-background-dispatcher)
12. [Async / sync boundaries](#12-async--sync-boundaries)
13. [Error handling, logging, and redaction](#13-error-handling-logging-and-redaction)
14. [Shutdown and cleanup](#14-shutdown-and-cleanup)
15. [Testing](#15-testing)
16. [How to add a route / schema / service / test](#16-how-to-add-a-route--schema--service--test)
17. [Known limitations](#17-known-limitations)

---

## 1. Entry point and app factory

The package is launched as a module:

```bash
.venv/bin/python -m agentflow
```

[`__main__.py`](../backend/agentflow/__main__.py) is the entry point. It binds
`127.0.0.1` (hard-coded; loopback only) on `AGENTFLOW_PORT` (default `8787`), prints a
banner with the local URL and `/docs`, and starts uvicorn against
`agentflow.app:app`:

```python
HOST = "127.0.0.1"
PORT = int(os.environ.get("AGENTFLOW_PORT", "8787"))
uvicorn.run("agentflow.app:app", host=HOST, port=PORT, log_level="info")
```

[`app.py`](../backend/agentflow/app.py) holds the **app factory** `create_app() -> FastAPI`
and creates the module-level `app = create_app()` that uvicorn imports. `create_app`
constructs the `FastAPI` instance with the product title/version and the lifespan hook,
adds middleware, includes the routers, defines `GET /api/health`, and — when a built
frontend exists — mounts it for single-port mode.

**Single-port mode.** If [`frontend/dist/`](../frontend/dist) exists with an
`index.html`, `create_app` mounts `/assets` as static files and registers a catch-all
`GET /{full_path:path}` that serves the SPA shell. The catch-all resolves the requested
path and verifies it stays inside `dist` (via `Path.is_relative_to`) before serving a
real file — Starlette URL-decodes the path, so `..` is attacker-controllable and this
guard prevents arbitrary file reads. Anything that is not a real file inside `dist`
falls back to `index.html`. When `dist/` is absent (dev), the backend serves the API
only and the Vite dev server on `:5180` proxies `/api`.

## 2. Lifespan: startup recovery, terminal sweep, shutdown

`create_app` wires an `@asynccontextmanager` lifespan (`_lifespan`) into the app. The
code before `yield` runs at startup; after `yield`, at shutdown.

**Startup — durable-state recovery.** A restart must never leave a run, queue item, or
task step stuck `running`. Before the dispatcher starts, `_lifespan` calls
`state_store.recover_workspace(ws)` for the current workspace (if one is selected). It
returns a summary; if anything was settled, a `warn` log entry is written. Recovery is
wrapped so it can never block startup. The same recovery also runs when a workspace is
selected (`POST /api/projects/workspace`), so switching workspaces heals leftover state
too.

**Startup — terminal orphan sweep.** PTY sessions are detached (`start_new_session=True`),
so a backend that was SIGKILLed or crashed before its shutdown hook can leave agent
process groups alive. `sweep_orphaned_sessions()` reaps any recorded session pidfiles
whose process looks like one of ours (no controlling tty plus a matching shell name)
and logs the count reaped.

**Shutdown.** The dispatcher task is cancelled, then `RUNNER.cancel_all()` cancels every
in-flight agent / dev-server run (so detached process groups — especially a preview
server holding a port — don't outlive the backend), then `TERMINALS.shutdown()`
terminates all PTY sessions. Each step is guarded so shutdown never raises.

The dispatcher itself is started in the lifespan as a single long-lived task:
`asyncio.create_task(queue_service.dispatcher_loop())` (see
[§11](#11-the-background-dispatcher)).

## 3. Middleware: CORS and the OriginGuard CSRF check

Two middlewares are added in `create_app`, both deriving their allow-list from
[`origins.py`](../backend/agentflow/origins.py) — the single source of truth shared by
CORS, the CSRF check, and the WebSocket origin check so they can never drift.
`LOCAL_ORIGINS` is the four self-origins: `localhost`/`127.0.0.1` on `:5180` (Vite dev)
and `:8787` (single-port).

- **`CORSMiddleware`** with `allow_origins=sorted(LOCAL_ORIGINS)`, all methods, all
  headers. CORS only governs whether a browser may *read* a cross-origin response.

- **`OriginGuardMiddleware`** (defined in `app.py`) is a `BaseHTTPMiddleware` that
  guards the CSRF gap CORS leaves open: a cross-site "simple request" (e.g. a
  `text/plain` POST) executes server-side regardless of CORS, and this app has no auth
  and runs commands. For mutating methods (`POST`/`PUT`/`PATCH`/`DELETE`) it reads the
  `Origin` (falling back to the `Referer`'s origin) and returns `403` if it is present
  but not in `LOCAL_ORIGINS`. A **missing** Origin is allowed — native clients, tests,
  and same-origin GET navigations carry none. This mirrors the WebSocket origin check
  in [`routes_terminals.py`](../backend/agentflow/api/routes_terminals.py), which rejects
  a foreign-origin handshake with close code `4403`.

`is_allowed_origin(origin)` returns `True` for an absent **or** allow-listed origin;
`origin_of(url)` reduces a URL to `scheme://host[:port]`.

## 4. Route organization

Routers live in [`backend/agentflow/api/`](../backend/agentflow/api), one
`routes_<area>.py` module per area, each exposing a module-level `router = APIRouter()`.
`create_app` mounts them under stable prefixes:

| Module | Prefix | Area |
| --- | --- | --- |
| [`routes_projects.py`](../backend/agentflow/api/routes_projects.py) | `/api/projects` | workspace selection, file tree/read/write, git, settings |
| [`routes_agents.py`](../backend/agentflow/api/routes_agents.py) | `/api/agents` | CLI detection, version checks, install, login, model selection |
| [`routes_tasks.py`](../backend/agentflow/api/routes_tasks.py) | `/api/tasks` | task CRUD, step run, full sequence, logs, exchanges |
| [`routes_usage.py`](../backend/agentflow/api/routes_usage.py) | `/api/usage` | traffic-control mode, provider health/limits, live usage, recommendations |
| [`routes_logs.py`](../backend/agentflow/api/routes_logs.py) | `/api/logs` | global activity log + currently running runs |
| [`routes_terminals.py`](../backend/agentflow/api/routes_terminals.py) | `/api/terminals` | PTY status, kill, and the per-provider WebSocket |
| [`routes_chat.py`](../backend/agentflow/api/routes_chat.py) | `/api/chat` | controller chat + direct per-agent chat |
| [`routes_queue.py`](../backend/agentflow/api/routes_queue.py) | `/api/queue` | execution queue: add/approve/remove/clear/retry/skip/reroute |
| [`routes_state.py`](../backend/agentflow/api/routes_state.py) | `/api` | durable events (polling + SSE), run ledger, approvals |
| [`routes_preview.py`](../backend/agentflow/api/routes_preview.py) | `/api/preview` | run the workspace dev server, report reachability |

`GET /api/health` is defined inline in `create_app`.

**Conventions every router follows.**

- The current workspace is resolved through `require_workspace()` (defined in
  `routes_projects.py` and imported by the others). It raises `HTTPException(409)` when
  no workspace is selected — this is the single chokepoint, so handlers never re-check.
- Handlers are thin: validate the request model, call a service, return the dict. Domain
  logic stays in the service layer.
- Service exceptions are translated to HTTP at the route: `FileNotFoundError → 404`,
  `ValueError`/`PermissionError → 400`, unknown provider/step → `404`. Routes raise
  `HTTPException` with a human-readable `detail`; they do not invent ad-hoc error JSON
  shapes for these cases.
- Request bodies are Pydantic models. Most live in
  [`models.py`](../backend/agentflow/models.py); a few small ones that are only used by
  one router (e.g. `SendRequest`, `QueueAddRequest`, `StartRequest`) are declared inline
  in that router.
- Sync vs async is chosen per handler — see [§12](#12-async--sync-boundaries).

## 5. Service layer

All behaviour lives in service modules at the top of the package; routers only adapt
HTTP to/from them. Each service owns one concern and reads/writes its own JSON under the
workspace.

| Service | Responsibility |
| --- | --- |
| [`config.py`](../backend/agentflow/config.py) | global + per-workspace config; `read_json`/`write_json`; routing, command templates, models, workspace selection |
| [`workspace.py`](../backend/agentflow/workspace.py) | file-tree scanning and safe text read/write (workspace-confined, no `.env`, text-only) |
| [`provider_probe.py`](../backend/agentflow/provider_probe.py) | the provider catalog (`PROVIDERS`); detect/version/status, one-click install, login launch, model listing |
| [`task_service.py`](../backend/agentflow/task_service.py) | tasks: folders, markdown handoff files, step execution, the full sequence, run history |
| [`queue_service.py`](../backend/agentflow/queue_service.py) | the execution queue and its dispatcher; controller consult requests |
| [`chat_service.py`](../backend/agentflow/chat_service.py) | controller and direct-agent chat; directive parsing → tasks/queue/commands |
| [`usage_service.py`](../backend/agentflow/usage_service.py) | per-workspace usage tracking; live quota from `codex`/`claude` |
| [`routing_service.py`](../backend/agentflow/routing_service.py) | budget-aware routing recommendations; `ROUTING_DECISIONS.md` |
| [`git_service.py`](../backend/agentflow/git_service.py) | read-only git info/diff plus explicit user-triggered stage/commit |
| [`process_runner.py`](../backend/agentflow/process_runner.py) | the subprocess runner (`RUNNER`) and the global activity log |
| [`terminal_service.py`](../backend/agentflow/terminal_service.py) | PTY-backed terminal sessions (`TERMINALS`) and orphan reaping |
| [`event_bus.py`](../backend/agentflow/event_bus.py) | in-memory, workspace-scoped live event bus (`BUS`) |
| [`state_store.py`](../backend/agentflow/state_store.py) | durable ledgers (events / runs / approvals) and restart recovery |
| [`headroom_service.py`](../backend/agentflow/headroom_service.py) | optional, fail-open Headroom token-saving proxy (Pillar 1) |
| [`prompt_templates.py`](../backend/agentflow/prompt_templates.py) | the prompt strings sent to each agent for each step/chat |
| [`agent_commands.py`](../backend/agentflow/agent_commands.py) | turn a command template + prompt + model into executable argv |
| [`chat_directives.py`](../backend/agentflow/chat_directives.py) | parse the controller's fenced directive blocks |
| [`workflow.py`](../backend/agentflow/workflow.py) | the step definitions (`STEP_DEFS`), I/O contract (`STEP_IO`), `FULL_SEQUENCE` |
| [`policy_service.py`](../backend/agentflow/policy_service.py) | command/action classifier (allow / require_approval / deny) |
| [`transitions.py`](../backend/agentflow/transitions.py) | explicit state machines for tasks/steps/queue/runs |
| [`contracts.py`](../backend/agentflow/contracts.py) | versioned Pydantic output contracts (Pillar 5) |
| [`redaction.py`](../backend/agentflow/redaction.py) | secret redaction for logs, previews, events |
| [`origins.py`](../backend/agentflow/origins.py) | the local-origin allow-list shared by CORS/CSRF/WS |
| [`paths.py`](../backend/agentflow/paths.py) | every filesystem location used by the app |

Cross-service cycles (e.g. `queue_service ↔ chat_service`, recovery touching queue +
task services) are broken with **function-local imports**, which is a deliberate
convention here rather than a smell.

## 6. Domain: state machine, policy, routing

### State machine — `transitions.py`

`transitions.py` declares explicit allowed-transition tables for four kinds: `task`,
`step`, `queue`, `run`, plus the known status sets and terminal-state sets. The single
predicate is:

```python
transitions.is_valid(kind, frm, to) -> bool
```

It is **permissive by design**: a no-op (`frm == to`) is allowed, and any transition
involving a status outside the known set is allowed so legacy/unknown values in older
`task.json` files don't block adoption. Only a *known→known* transition that is not in
the table is rejected. Callers (notably `task_service._set_step_state` and
`queue_service._apply_status`) use it as a validated chokepoint: an illegal transition
is **logged** as an error but still applied, so a bad transition never wedges the queue.

### Policy — `policy_service.py`

`policy_service.classify_action(command, workspace, …) -> PolicyResult` is the single
source of truth for whether a command the controller proposes may run. It produces one
of three decisions:

- **`deny`** — shell operators (`| > < ; && || ` $( &`), env-var prefixes, blocked
  binaries (`sudo`, `bash`, `dd`, …), inline-eval interpreters (`python -c`, `node -e`),
  path traversal / paths outside the workspace, `rm -rf /`, and known exec-bypass vectors
  (`git -c`, `tar --checkpoint-action`/`--to-command`/`-I`). Denied actions never run.
- **`require_approval`** — shared/remote-state changes: `git push`/`pull`/`fetch`,
  `gh`, `brew`/`pip`/`docker`/etc., dependency installs (`npm install`), package
  exec (`npx`, `npm exec`), deploys, and any script-running interpreter / code runner
  (`make`, `awk`, `sed`). These create a durable approval rather than auto-running.
- **`allow`** — everything else inside the workspace.

Commands are parsed with `shlex` and **never** interpolated into a shell. A backward-
compatible `deny_reason()` wrapper (re-exported as `chat_service.command_denied`)
returns a reason only for hard denials, preserving the legacy denylist contract.
See [adr/0001-auto-run-policy-allowlist.md](adr/0001-auto-run-policy-allowlist.md).

### Routing — `routing_service.py`

`routing_service.recommend(usage, …)` applies the budget rules to current provider
health (`green`/`yellow`/`red`) and the orchestration mode (`maximum_quality`,
`balanced`, `budget_saver`, `manual_approval`) to produce advisory routing guidance,
warnings, and a budget-context header that is fed into agent prompts. It also writes and
appends `ROUTING_DECISIONS.md` in each task folder. The roles → providers map lives in
config (`DEFAULT_ROUTING`: orchestrator→antigravity, pm→codex, engineer→claude,
qa→antigravity) and steps map to roles via `workflow.STEP_DEFS`.

## 7. Persistence: JSON ledgers and atomic writes

**There is no database.** All state is plaintext JSON, written atomically.

**Atomic writes.** `config.write_json(path, data)` writes to a temp file in the target
directory and `os.replace`s it into place, so a reader never sees a half-written file.
`config.read_json(path, default)` returns `default` on a missing file or decode error.
Every persistence path in the backend goes through these two functions.

**Global state** (`~/.agentflow/`, locations in
[`paths.py`](../backend/agentflow/paths.py)):

- `config.json` — current workspace, routing, command templates, models, headroom
- `providers.json` — cached provider-check results
- `run/terminals/*.session` — pidfiles for orphan reaping
- `bin/` — generated login `.command` scripts (macOS)

**Per-workspace state** (`<workspace>/.agentflow/`):

- `config.json`, `usage.json`
- `tasks/<task_id>/` — `task.json` + the numbered markdown handoff files + `logs/`
- `events.json` — durable, bounded (2000), schema-versioned timeline
- `runs.json` — the run ledger (bounded 200, never prunes a `running` run)
- `approvals.json` — pending/resolved approvals
- `queue.json`, `chat.json`

`.agentflow/` is kept out of the user's repo with a self-contained `.gitignore` (`*`).

**The durability split** ([`event_bus.py`](../backend/agentflow/event_bus.py) vs
[`state_store.py`](../backend/agentflow/state_store.py)):

- **Structural transitions** (run/queue/task/approval lifecycle) are persisted to
  `events.json` by `state_store.append_event`, which *also* mirrors the event onto the
  live bus so it streams. These survive restart and drive recovery.
- **High-frequency text deltas** are **not** persisted per chunk; they stream live
  through `BUS` only (the full redacted output is written to the run's log file).
- The schema-versioned ledgers carry a `schemaVersion` and a monotonic `cursor`;
  `_load_doc` repairs a missing/stale shape and is the forward-migration hook.

**Recovery.** `state_store.recover_workspace(workspace)` is idempotent. For every
persisted `running` run not still owned by `RUNNER`, it settles the run as
`failed`/`backend_restart`, fails its queue item as interrupted, blocks later queued
items of that task, and unsticks task steps that claim `running` with no live run. A
clean workspace recovers to all-zeros. (`_pid_alive` only refines the wording — a
restart can no longer manage or capture the old process either way.)

## 8. Schemas: request models and output contracts

Two distinct schema layers, both Pydantic v2:

- **Request models** — [`models.py`](../backend/agentflow/models.py) holds the inbound
  request bodies (`WorkspaceRequest`, `TaskCreateRequest`, `RunStepRequest`,
  `SettingsUpdateRequest`, `GitCommitRequest`, …) with field constraints (`min_length`,
  `max_length`). One-off bodies used by a single router are declared inline in that
  router. These validate what the **UI sends in**.

- **Output contracts** — [`contracts.py`](../backend/agentflow/contracts.py) is the
  Pillar 5 deterministic semantic layer: versioned, `kind`-discriminated records for
  controller directives (`task`/`queue`/`run`/`done`/`needs_user`), and for
  results/summaries (`command_summary`, `test_summary`, `failure`, `approval_request`,
  `task_summary`, `agent_handoff`, `token_efficiency_report`). Every contract carries a
  `version` and a `kind`. The entry point is:

  ```python
  contracts.validate(kind, data) -> (model | None, FailureRecord | None)
  ```

  It **never raises** for bad input — an unknown kind, an unsupported version, or a
  schema violation returns a structured `FailureRecord` to surface, not an exception.
  [`chat_directives.py`](../backend/agentflow/chat_directives.py) bridges the legacy
  fenced-block parsers to these contracts (`controller_directive_records`) so controller
  decisions can be emitted as typed records rather than re-sniffed from prose.

## 9. The subprocess runner

[`process_runner.py`](../backend/agentflow/process_runner.py) is the heart of the
backend. The module-level singleton `RUNNER = ProcessRunner()` owns every child process
the backend spawns: agent runs, the controller/chat runs, controller-issued commands,
provider probes, git, and the preview dev server.

**Records.** Each run is a `RunRecord` (run id, argv, cwd, status, exit code, timing,
captured stdout/stderr parts, `stream_kind`, provider/task/step, `failure_kind`, pid,
prompt file, log file, headroom flag). It projects two views: `to_dict()` (UI, larger
output tail) and `to_ledger()` (durable, tailed + redacted) — full output lives only in
the per-run log file.

**Streaming.** `start(argv, cwd, …)` spawns with `asyncio.create_subprocess_exec`,
`start_new_session=True` (own process group, for clean cancellation), `stdin=DEVNULL`,
and a child env with `PORT`/`AGENTFLOW_PORT` stripped (so a spawned dev server can't
bind on top of the backend). It returns immediately; output is consumed by a background
task. Passing `workspace=` makes the run **stream live events** to the
[`event_bus`](../backend/agentflow/event_bus.py) (`run.output`/`run.stderr`,
`chat.delta`, `controller.delta`, `command.*`, lifecycle, and a `run.heartbeat` every
10s while alive). Quiet probes/git omit `workspace=` and stay silent.

**Delta-boundary redaction.** `_read_stream` reads 4 KiB chunks and holds the tail up to
the last whitespace before emitting (`_split_emittable`), so a secret — which never
contains whitespace under the redaction patterns — is never split across two deltas and
emitted half-masked. A pathological whitespace-less blob is force-flushed past 64 KiB.
In-memory capture is bounded at ~2 MB per stream, after which output is marked
`truncated`.

**Cancel.** `cancel(run_id)` marks the record cancelled, `SIGTERM`s the whole process
group, and schedules a `SIGKILL` backstop after 4s. `cancel_all()` cancels every live
run and is called on shutdown.

**Watchdog (headroom for the lane).** Agent/chat/command runs are started with
`max_runtime=AGENT_RUN_TIMEOUT` (1200s / 20 min). `_watchdog` cancels a wedged run so a
CLI stuck on auth/network can't hold its provider lane (and the autonomous queue)
forever, refining the failure kind to `timeout`. The preview dev server is deliberately
started **without** a watchdog — it is meant to run indefinitely.

**Headroom injection (Pillar 1).** Before spawning, `start` calls
`headroom_service.proxy_env(provider)` and merges the result into the child env. When
Headroom is enabled and its proxy is reachable, this injects the provider's base-URL env
var (`ANTHROPIC_BASE_URL` for claude, `OPENAI_BASE_URL` for codex) so the CLI's LLM
calls route through the proxy; otherwise it returns `{}` and the run goes direct
(**fail-open**). Antigravity is intentionally not routed.

**Background-task hygiene.** Fire-and-forget tasks (consume, heartbeat, watchdog, hard
kill) are tracked in `_bg_tasks` with a strong reference until done, so the event loop
can't GC them mid-flight.

**Activity log.** The module also owns the global, bounded `LOG_BUFFER` and
`add_log_entry(...)` shown on the Logs page (summaries clipped, output redacted) — see
[§13](#13-error-handling-logging-and-redaction).

## 10. PTY terminals

[`terminal_service.py`](../backend/agentflow/terminal_service.py) provides real
pseudo-terminal sessions so the CLI panes behave like genuine terminals (ANSI colors,
TUIs, job control). `TERMINALS = TerminalManager()` keys one `TerminalSession` per
`<workspace>::<provider>`.

Each session opens a `pty.openpty()` master/slave pair and spawns the user's `$SHELL -i`
(default `/bin/bash`) with `start_new_session=True` (own process group) but **without**
claiming a controlling terminal — that keeps job control effectively off so keystrokes
flow straight into an auto-launched TUI like `agy`. The configured CLI is auto-launched
once after a short delay (`launch_command(provider)`); Antigravity is launched bare on
purpose (a starter prompt handed to `agy` during its auth/init window is swallowed). PTY
output is buffered in a bounded scrollback (256 KB) and fanned out to every connected
WebSocket client; sessions outlive a single connection, and the scrollback is replayed
on (re)connect.

The WebSocket lives in [`routes_terminals.py`](../backend/agentflow/api/routes_terminals.py):
server→client frames are raw binary; client→server control frames are JSON
(`input`/`resize`/`kill`). The handshake checks `Origin` against the shared allow-list
(close `4403` on a foreign browser origin). The scrollback snapshot is taken and the
client queue registered in one synchronous step (no `await` between) so no bytes are
lost in the gap on reconnect.

**Orphan reaping.** Sessions are detached, so a crashed/SIGKILLed backend can leak
process groups. Each session drops a pidfile under `~/.agentflow/run/terminals/`;
`sweep_orphaned_sessions()` runs on startup and `SIGKILL`s any recorded pid that still
looks like one of ours (no controlling tty + matching shell name — guards against pid
reuse).

## 11. The background dispatcher

[`queue_service.dispatcher_loop()`](../backend/agentflow/queue_service.py) is the single
long-lived background task started in the lifespan. Every `TICK_SECONDS` (1.5s) it calls
`tick(workspace)` for the current workspace, wrapped so the loop survives any exception.

`tick` does three things in order:

1. **`_finalize_running`** — settle queue items whose run has finished (done /
   cancelled / failed), block later queued steps of a task that just failed, request a
   controller consult for orchestrated tasks, and prune terminal history.
2. **`_process_consults`** — run at most one pending controller consult when the
   controller provider is free and the user isn't mid-conversation (dropped in Manual
   Approval mode).
3. **`_pick_candidate` + `dispatch_item`** — pick the first dispatchable queued item
   (queue order, one run per provider, intra-task order preserved, skipping tasks with a
   busy provider or a running full sequence) and dispatch it. In Manual Approval mode the
   candidate is flipped to `awaiting_approval` instead of running.

The queue persists to `queue.json`, so it survives restart (and recovery settles
anything left `running`).

## 12. Async / sync boundaries

The app mixes `async def` and `def` route handlers deliberately:

- **`async def`** handlers are used wherever the work awaits I/O the runner exposes as
  coroutines — anything that calls `RUNNER.start`/`run_and_wait`/`cancel`, git
  (`git_service` shells out via the runner), provider checks/installs, chat, queue
  dispatch/approve, the SSE stream, and the WebSocket. These run **on the event loop**;
  they must not block it.
- **plain `def`** handlers are used for fast, synchronous JSON work (config read/write,
  listing tasks, reading the file tree, usage mutations, settings). FastAPI runs every
  sync route in its **threadpool**, so these don't block the loop either.

Because sync routes execute in worker threads while async coroutines run on the loop, the
shared in-memory structures they both touch are guarded: `event_bus.EventBus` assigns
event ids and appends under a `threading.Lock` (publishers run from both the loop and
the threadpool). The durable JSON ledgers are not lock-synchronized across concurrent
writers — see [§17](#17-known-limitations).

## 13. Error handling, logging, and redaction

**Error handling.** Routes translate expected service exceptions to `HTTPException`
(see [§4](#4-route-organization)). Background work that must never crash the process —
the dispatcher loop, `on_complete` hooks, startup recovery, the terminal sweep, consult
post-processing — catches broadly (`# noqa: BLE001`) and records the failure via
`add_log_entry(..., status="error")` rather than propagating. Live data that is
best-effort (e.g. `claude_live_usage`) fails silently to a "manual limit" note.

**Logging.** `add_log_entry(source, summary, …)` appends to the bounded in-memory
`LOG_BUFFER` (500 entries) surfaced at `GET /api/logs`; `clear_log_view()` hides older
entries from the view without dropping them. Structural transitions additionally go to
the durable `events.json` via `state_store.append_event`, which mirrors them onto the
live event bus.

**Redaction.** [`redaction.py`](../backend/agentflow/redaction.py) is a
defense-in-depth boundary: secrets must never be persisted or broadcast, and redaction
happens **server-side**, never in the browser. `redact(text)` masks PEM key blocks,
provider token literals (GitHub PAT, `gh*_`, `sk-`, Slack `xox*`, AWS `AKIA…`, Google
`AIza…`), bearer tokens, `KEY=value`/`KEY: value` secret forms, and URL-embedded
credentials. `redact_data(value)` walks a JSON-ish structure recursively so a secret in
a structured `data` / `action` payload is masked too. Redaction is applied at every
egress: the event bus (`detail`, `textDelta`, `data`), `state_store` (before persisting
events/approvals — though the raw action is kept on disk so an approved command can be
replayed verbatim), the activity log, run log files, command previews, git output, file
previews, and chat messages.

## 14. Shutdown and cleanup

On shutdown the lifespan (see [§2](#2-lifespan-startup-recovery-terminal-sweep-shutdown))
cancels the dispatcher, then `RUNNER.cancel_all()` (SIGTERM each process group, SIGKILL
backstop), then `TERMINALS.shutdown()` (terminate every PTY session, force-killing a
group that ignores SIGTERM/EOF after ~1s). If the backend is SIGKILLed and never runs
this hook, the next startup heals the consequences: `recover_workspace` settles stuck
durable state and `sweep_orphaned_sessions` reaps leaked terminal process groups.

## 15. Testing

Tests live in [`backend/tests/`](../backend/tests) (pytest, ~165 tests, ruff + mypy in
CI). Run them with the venv interpreter:

```bash
.venv/bin/python -m pytest backend/tests        # or: make test-backend
make verify                                      # format-check + lint + typecheck + test + build (mirrors CI)
```

[`conftest.py`](../backend/tests/conftest.py) provides shared fixtures (notably a
temporary workspace). Test modules mirror the service they cover —
`test_policy_service.py`, `test_transitions.py`, `test_state_store.py`,
`test_recovery.py`, `test_queue_service.py`, `test_task_service.py`,
`test_chat_service.py`, `test_process_cancel.py`, `test_run_lifecycle.py`,
`test_streaming.py`, `test_redaction.py` / `test_redaction_payloads.py`,
`test_contracts.py`, `test_headroom_service.py`, `test_csrf.py`,
`test_routes_terminals.py`, `test_routes_state.py`, and `test_pillars.py`, among others.
Routes are exercised through FastAPI's `TestClient`; subprocess behaviour is tested
against short real commands rather than heavy mocking. The frontend has its own suite
(`npm --prefix frontend run test`, vitest).

## 16. How to add a route / schema / service / test

**Add a service.** Create `backend/agentflow/<name>_service.py`. Read/write state only
through `config.read_json`/`write_json` (atomic) under a path defined in
[`paths.py`](../backend/agentflow/paths.py) — add a helper there rather than hard-coding
a path. Keep all domain logic in the service; never reach into HTTP. If you must call
another service that imports you back, use a function-local import. Redact before
anything is persisted, logged, or emitted. Record state changes through the existing
chokepoints (`state_store.append_event`, `add_log_entry`) and validate status changes
with `transitions.is_valid`.

**Add a route.** Either extend the matching `routes_<area>.py` or add a new
`routes_<area>.py` with a module-level `router = APIRouter()` and include it in
`create_app` under a `/api/...` prefix with a `tags=[...]`. Resolve the workspace with
`require_workspace()`. Keep the handler thin: validate → call the service → return.
Translate `FileNotFoundError → 404` and `ValueError`/`PermissionError → 400` via
`HTTPException`. Choose `async def` if the handler awaits the runner/git/network;
otherwise plain `def` (FastAPI threadpools it).

**Add a request schema.** Add a Pydantic model to
[`models.py`](../backend/agentflow/models.py) (or inline in the router if it is used by
exactly one route) with field constraints. For a new *output* shape that the controller
or an agent produces, add a versioned, `kind`-discriminated contract to
[`contracts.py`](../backend/agentflow/contracts.py), register it in `_REGISTRY`, and
validate through `contracts.validate` so bad input fails safely.

**Add a test.** Create `backend/tests/test_<name>.py`, reuse the workspace fixture from
`conftest.py`, and drive routes through `TestClient`. Run `make verify` before opening a
PR (it mirrors CI). See [ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md) and
[DEVELOPMENT.md](DEVELOPMENT.md).

## 17. Known limitations

The most important backend-internal one: the durable JSON ledgers
(`events.json`, `runs.json`, `approvals.json`, `queue.json`, `chat.json`, `task.json`)
use atomic single-writer writes (`config.write_json`) but are **not** synchronized
across concurrent writers. The dispatcher loop (event loop), sync route handlers
(threadpool), and `on_complete` hooks can read-modify-write the same file from different
threads, so a last-writer-wins race can drop a concurrent update. This is acceptable for
the local, single-user design (one human, low write contention) but is a real
constraint. This and the rest are tracked in [LIMITATIONS.md](LIMITATIONS.md); the
security model is in [SECURITY.md](SECURITY.md) and operational caveats in
[OPERATIONS.md](OPERATIONS.md).
