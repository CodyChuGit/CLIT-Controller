# Architecture

CLIT Controller IDE (package `agentflow`, product name "Command Line Interface Terminal
Controller", repo `AgentComposer`). This document describes what the code actually does.
Where it diverges from the design notes in [docs/orchestrator-backend](orchestrator-backend/),
that is called out explicitly.

## 1. Overview

CLITC is a **local-first** desktop-style web app that orchestrates the user's own CLI
coding agents — `claude`, `codex`, and `agy`/`antigravity` — as subprocesses. It does
not call any model API itself; every model turn is a real invocation of an installed CLI
in the selected workspace folder. The backend also runs interactive PTY terminals over
WebSockets, reads/writes the workspace git tree, tracks approximate provider usage, and
streams all live output to the UI over Server-Sent Events with a polling fallback.

- **Backend**: FastAPI ([app.py](../backend/agentflow/app.py)) on a single asyncio event
  loop, served by uvicorn ([__main__.py](../backend/agentflow/__main__.py)).
- **Frontend**: React 18 + Vite 5, TypeScript, Tailwind. Entry
  [main.tsx](../frontend/src/main.tsx) → [App.tsx](../frontend/src/App.tsx).

### Topology

| Mode | How it runs | Ports |
|---|---|---|
| **Single-port (production / installed)** | Backend serves the API *and* the built SPA from `frontend/dist`. [app.py](../backend/agentflow/app.py) mounts `/assets` and a catch-all `/{full_path}` SPA route when `frontend/dist/index.html` exists. | `:8787` only |
| **Dev** | Backend on `:8787`; Vite dev server on `:5180` proxies `/api` (with `ws:true` for terminal WebSockets) to the backend. Run via [scripts/dev.sh](../scripts/dev.sh). | backend `:8787` + Vite `:5180` |

The backend binds **`127.0.0.1` only** ([__main__.py](../backend/agentflow/__main__.py),
`HOST = "127.0.0.1"`); the port is overridable with `AGENTFLOW_PORT`. The SPA catch-all
resolves the candidate path and verifies it stays inside `dist` before serving, so the
static handler cannot be used for arbitrary file reads.

> Note: the title strings say both "Terminal Controller" (code/UI) and, in
> [DESIGN.md](../DESIGN.md), "Traffic Controller". Throughout this doc "controller" /
> "traffic control" refers to the orchestrator role (the agent in the `orchestrator`
> routing slot that drives tasks).

## 2. Request / data flow

```text
                 User / browser
                       │
        ┌──────────────┴───────────────┐
        │  React UI (pages/, components/)│   useSyncExternalStore-backed
        │  - imperative calls: api.ts    │   stream store (stream.tsx)
        │  - live events:     stream.tsx │   localStorage (persist.ts)
        └───────┬───────────────┬────────┘
   fetch /api/* │               │ SSE  GET /api/events/stream  (+ poll /api/events)
   WS /api/...  │               │      EventSource, resume-by-cursor
   /ws          │               │
        ┌───────▼───────────────▼────────────────────────────────┐
        │ TRANSPORT — FastAPI routers  api/routes_*.py            │
        │  projects agents tasks usage logs terminals chat queue  │
        │  state preview   (+ require_workspace() guard)          │
        └───────┬─────────────────────────────────────────────────┘
                │
        ┌───────▼─────────────────────────────────────────────────┐
        │ APPLICATION / SERVICES                                    │
        │  task_service · chat_service · queue_service             │
        │  provider_probe · usage_service · git_service · workspace │
        └───────┬─────────────────────────────────────────────────┘
                │
        ┌───────▼─────────────────────────────────────────────────┐
        │ DOMAIN                                                    │
        │  transitions (state machines) · policy_service           │
        │  routing_service · workflow (steps) · chat_directives     │
        │  agent_commands (template → argv) · prompt_templates      │
        └───────┬─────────────────────────────────────────────────┘
                │
        ┌───────▼─────────────────────────────────────────────────┐
        │ INFRASTRUCTURE / CORE                                     │
        │  process_runner (RUNNER) · terminal_service (TERMINALS)   │
        │  state_store (durable ledgers) · event_bus (BUS)         │
        │  config · paths · redaction                               │
        └───────┬───────────────────────┬─────────────────────────┘
                │                        │
        subprocesses (claude/         filesystem
        codex/agy, git, dev server,   ~/.agentflow  (global config, providers cache,
        installers); PTY shells       run/terminals pidfiles, login scripts)
                                      <workspace>/.agentflow  (per-workspace state)
```

The dispatcher loop ([queue_service.dispatcher_loop](../backend/agentflow/queue_service.py))
runs continuously alongside request handling, advancing the queue without an HTTP trigger.
Both the request path and the dispatcher publish to the same [event_bus](../backend/agentflow/event_bus.py),
which is what the SSE/polling stream serves.

## 3. Backend module map

| Module | Responsibility | Layer |
|---|---|---|
| [app.py](../backend/agentflow/app.py) | App factory, CORS, router mounting, lifespan (startup recovery + orphan sweep, dispatcher task), SPA static serving | transport |
| [__main__.py](../backend/agentflow/__main__.py) | uvicorn entrypoint, localhost binding, port | transport |
| [api/routes_projects.py](../backend/agentflow/api/routes_projects.py) | Workspace select, file tree/read/write, git info/diff/status/stage/commit, settings; `require_workspace()` guard | transport |
| [api/routes_agents.py](../backend/agentflow/api/routes_agents.py) | Provider list/check/install/login, per-agent model | transport |
| [api/routes_tasks.py](../backend/agentflow/api/routes_tasks.py) | Task CRUD, run step / run-full, stop, logs, exchanges, open-folder | transport |
| [api/routes_queue.py](../backend/agentflow/api/routes_queue.py) | Queue read/add/approve/remove/clear/retry/skip/reroute | transport |
| [api/routes_chat.py](../backend/agentflow/api/routes_chat.py) | Controller chat + direct-agent chat send/stop/clear | transport |
| [api/routes_usage.py](../backend/agentflow/api/routes_usage.py) | Orchestration mode, provider health/limits, live usage, recommendations | transport |
| [api/routes_state.py](../backend/agentflow/api/routes_state.py) | `GET /events` (poll), `GET /events/stream` (SSE), run lookup, approvals approve/reject | transport |
| [api/routes_terminals.py](../backend/agentflow/api/routes_terminals.py) | Terminal status, kill, and the `/{provider}/ws` PTY WebSocket (with WS origin allowlist) | transport |
| [api/routes_logs.py](../backend/agentflow/api/routes_logs.py) | Global activity log + currently-running run snapshots | transport |
| [api/routes_preview.py](../backend/agentflow/api/routes_preview.py) | Dev-server start/stop, preview URL (localhost-only), TCP reachability check | transport |
| [models.py](../backend/agentflow/models.py) | Pydantic request bodies + literals (`OrchestrationMode`, `Health`) | transport |
| [task_service.py](../backend/agentflow/task_service.py) | Task folders/markdown handoff files, `run_step`, `run_full_sequence`, step-state chokepoint, artifact/code-change detection, run projection | application |
| [chat_service.py](../backend/agentflow/chat_service.py) | Controller + direct chat runs, `orchestrator_consult` loop, directive execution, direct command runs | application |
| [queue_service.py](../backend/agentflow/queue_service.py) | Execution queue, `dispatcher_loop`/`tick`, single-flight per provider, intra-task ordering, consults, retry/skip/reroute | application |
| [provider_probe.py](../backend/agentflow/provider_probe.py) | CLI detection (`which`/`resolve_executable`), version/status checks, one-click install, login launch, model listing, cache | application |
| [usage_service.py](../backend/agentflow/usage_service.py) | Per-workspace `usage.json`, window resets, `record_call`, manual health, live usage (codex session files, `claude -p /usage`) | application |
| [git_service.py](../backend/agentflow/git_service.py) | Read-only git info/diff/status (porcelain parse) + explicit stage/unstage/commit | application |
| [workspace.py](../backend/agentflow/workspace.py) | Bounded file-tree scan; safe text read/write (workspace-confined, `.env` refused) | application |
| [transitions.py](../backend/agentflow/transitions.py) | State-machine tables for task/step/queue/run; `is_valid` (permissive about unknown statuses) | domain |
| [policy_service.py](../backend/agentflow/policy_service.py) | Command classification: `allow` / `require_approval` / `deny` (shell operators, traversal, eval, blocked binaries, remote/install actions) | domain |
| [routing_service.py](../backend/agentflow/routing_service.py) | Budget-aware routing recommendations + `ROUTING_DECISIONS.md` writing | domain |
| [workflow.py](../backend/agentflow/workflow.py) | `STEP_DEFS`, `STEP_IO`, `FULL_SEQUENCE` (the pipeline contract) | domain |
| [chat_directives.py](../backend/agentflow/chat_directives.py) | Parse fenced ` ```agentflow-task/queue/run/done/needs-user ` blocks from agent output | domain |
| [agent_commands.py](../backend/agentflow/agent_commands.py) | `build_argv`: template (`{prompt}`/`{model}`) → argv via shlex; provider-busy result | domain |
| [prompt_templates.py](../backend/agentflow/prompt_templates.py) | Prompt construction + initial task markdown files | domain |
| [process_runner.py](../backend/agentflow/process_runner.py) | `RUNNER`: real subprocess lifecycle, stream capture + delta emit, cancel/heartbeat, per-run log files, in-memory `RunRecord`s, global activity log | infrastructure |
| [terminal_service.py](../backend/agentflow/terminal_service.py) | `TERMINALS`: PTY sessions, scrollback fan-out, orphan reaping via pidfiles | infrastructure |
| [state_store.py](../backend/agentflow/state_store.py) | Durable ledgers (`events.json`, `runs.json`, `approvals.json`), `recover_workspace` | infrastructure |
| [event_bus.py](../backend/agentflow/event_bus.py) | `BUS`: in-memory, lock-guarded ring buffer of live events with monotonic ids; redaction | infrastructure |
| [config.py](../backend/agentflow/config.py) | Global + per-workspace config, command templates, routing, models; atomic JSON writes | core |
| [paths.py](../backend/agentflow/paths.py) | All filesystem locations (`~/.agentflow`, `<workspace>/.agentflow`) | core |
| [redaction.py](../backend/agentflow/redaction.py) | Secret redaction (tokens, keys, KEY=value, URL creds) — applied before persist/broadcast | core |

## 4. Frontend module map

Entry [main.tsx](../frontend/src/main.tsx) mounts [App.tsx](../frontend/src/App.tsx), which
holds the app shell (activity bar · main page · resizable chat dock · status bar), owns
editor tab state, and wraps everything in `EventStreamProvider`. A production build also
registers a service worker (`/sw.js`) for the PWA shell.

**API client** — [api.ts](../frontend/src/api.ts): thin typed `fetch` wrapper over `/api`,
throwing `ApiError(status, detail)`; one `api.*` method per endpoint. Imperative
request/response only (no streaming).

**Stream store** — [stream.tsx](../frontend/src/stream.tsx): a single `StreamStore`
(plain class) exposed through `useSyncExternalStore` hooks. `EventStreamProvider` opens one
SSE connection to `/api/events/stream` per workspace, falls back to polling `/api/events`,
dedupes/resumes by event `id` (cursor), accumulates per-run stdout/stderr deltas (capped),
and coalesces re-renders to one `requestAnimationFrame`. Hooks: `useConnection`,
`useStructuralRevision` (bumps on structural events so polled snapshots refetch
event-driven), `useRunStream(runId)`, `useRecentEvents`.

**Persistence** — [persist.ts](../frontend/src/persist.ts): `loadState`/`saveState` over
`localStorage` under the `agentflow.` prefix (current page, open editor tabs per workspace,
panel state). No app data lives only in the browser; the backend is authoritative.

**Types** — [types.ts](../frontend/src/types.ts): shared DTO/event types mirroring backend
responses (`StreamEvent`, `RunStream`, `QueueState`, `TaskDetail`, etc.).

| Pages ([pages/](../frontend/src/pages/)) | Renders |
|---|---|
| `ProjectsPage` | VS Code-style Explorer: workspace path, git/source-control, file tree, tabbed editor, output panel |
| `AgentsPage` | Provider cards: installed/version, model picker, install/login/check |
| `TasksPage` (+ `pages/tasks/`) | Task hub: flow chart, state/handoff timeline, queue strip, step chats, approvals, diffs |
| `TerminalsPage` | Three xterm.js PTY panes (codex/claude/antigravity) over WebSocket |
| `PreviewPage` | Embedded localhost iframe + dev-server controls |
| `UsagePage` | Provider quota table, live windows, health toggles, budget mode, recommendations |
| `LogsPage` | Live event feed + structured activity log |
| `SettingsPage` | Routing roles, command templates, config-path display |

**Components** ([components/](../frontend/src/components/)) — shell/nav (`ActivityBar`,
`StatusBar`, `DragHandle`), chat (`ChatPanel`, `Composer`, `CommandPalette`), display
(`TimelineCard`, `RawDetail`, `Markdown`, `SmoothStreamingText`, `LogConsole`, `TaskViews`,
`StatusBadge`, `ArtifactChip`, `UsageHealthBadge`), files/git (`FileTree`, `CodeReader`,
`SourceControlPanel`, `FileTypeIcon`), providers/usage (`ProviderCard`,
`RoutingRecommendationCard`, `BudgetModePicker`), and primitives (`icons`, `ui`).
`ChatPanel` consumes `useRunStream`/`useStructuralRevision`/`useRecentEvents` so controller
and direct-agent transcripts stream live and refetch on structural change.

**Lib** ([lib/](../frontend/src/lib/)) — `displayModel.ts` builds the structured "card"
projection (severity/title/chips/artifacts) shared by the dock and Tasks; `taskFormat.ts`
has pure formatting helpers (prompt parsing, output summarizing, durations).

**Terminals transport** — [TerminalsPage](../frontend/src/pages/TerminalsPage.tsx) uses
xterm.js + FitAddon, connects to `/api/terminals/{provider}/ws`, sends keystrokes as
`{type:"input",data}` and resizes as `{type:"resize",rows,cols}` JSON frames, writes binary
output to the terminal, and auto-reconnects on unexpected close.

## 5. State & persistence

Two roots, both atomic-write JSON (`config.write_json` = tmp file + `os.replace`):

**Global — `~/.agentflow/`** ([paths.py](../backend/agentflow/paths.py)):

| File / dir | Contents |
|---|---|
| `config.json` | `currentWorkspace`, `routing` (role→provider), `commandTemplates`, `models` ([config.py](../backend/agentflow/config.py)) |
| `providers.json` | Cached provider check results (version/status/models) |
| `bin/` | Generated `login-<provider>.command` scripts launched in Terminal (macOS) |
| `run/terminals/` | `<pid>.session` pidfiles used to reap orphaned PTY process groups |

**Per-workspace — `<workspace>/.agentflow/`**:

| File / dir | Owner | Contents |
|---|---|---|
| `.gitignore` (`*`) | [config.py](../backend/agentflow/config.py) | Keeps `.agentflow/` out of the user's repo |
| `config.json` | [config.py](../backend/agentflow/config.py) | `workspacePath`, per-workspace `routing`, `devCommand`, `previewUrl` |
| `usage.json` | [usage_service.py](../backend/agentflow/usage_service.py) | Orchestration mode, per-provider health/limits/window counters, savings counters |
| `tasks/<id>/` | [task_service.py](../backend/agentflow/task_service.py) | `task.json` (steps, events, fullSequence), markdown handoff files, `ROUTING_DECISIONS.md`, `logs/` (`*.log`, `*.prompt.txt`) |
| `events.json` | [state_store.py](../backend/agentflow/state_store.py) | Durable, schema-versioned, bounded (2000) timeline of structural transitions; cursor for polling |
| `runs.json` | [state_store.py](../backend/agentflow/state_store.py) | Durable run ledger (recovery-oriented projection; never prunes a `running` run) |
| `approvals.json` | [state_store.py](../backend/agentflow/state_store.py) | Pending/resolved approvals for risky actions |
| `queue.json` | [queue_service.py](../backend/agentflow/queue_service.py) | Queue items (survives restart) |
| `chat.json` | [chat_service.py](../backend/agentflow/chat_service.py) | Controller transcript (`messages`) + per-agent direct channels |

**Authoritative split**: markdown + `task.json` stay authoritative for human reading; the
`events`/`runs`/`approvals` ledgers are authoritative for *recovery*. (The design notes in
[02-architecture-contracts.md](orchestrator-backend/02-architecture-contracts.md) propose a
single `state.db`; the code instead uses the per-purpose JSON files above, honoring the
"atomic writes + schema version + recovery migration" contract without SQLite.)

**Durable event ledger + cursor-resume.** [state_store.append_event](../backend/agentflow/state_store.py)
writes a structural event to `events.json` *and* mirrors it to the in-memory
[event_bus](../backend/agentflow/event_bus.py). High-frequency text deltas (`run.output`,
`chat.delta`, …) are emitted to the bus only — never persisted per-chunk; full redacted
output lives in each run's `logs/*.log`. The SSE endpoint
([routes_state.events_stream](../backend/agentflow/api/routes_state.py)) honors `cursor`
and the `Last-Event-ID` header so a reconnect/refresh never duplicates text. There are two
distinct cursors: the bus's process-monotonic `id` (live stream) and the `events.json`
`cursor` (durable timeline); the live SSE/poll path reads the **bus**.

**Startup recovery.** On lifespan startup (and on workspace selection),
[state_store.recover_workspace](../backend/agentflow/state_store.py) settles every persisted
`running` run not owned by the current `RUNNER` as `failed` / `failureKind=backend_restart`,
fails the corresponding queue items, blocks later queued steps of interrupted tasks, and
unsticks task steps — so nothing is stuck `running` after a restart. The lifespan hook also
sweeps orphaned PTY sessions left by a crashed prior backend.

## 6. Concurrency model

- **Single asyncio event loop** runs the FastAPI app. `async def` routes run on the loop;
  plain `def` routes run in FastAPI's threadpool. Because both can publish events,
  [event_bus.EventBus](../backend/agentflow/event_bus.py) guards id assignment + buffer
  append with a `threading.Lock`, and redaction happens at publish time.
- **Dispatcher loop** — [queue_service.dispatcher_loop](../backend/agentflow/queue_service.py)
  is a background `asyncio.Task` started in the lifespan hook. Every `TICK_SECONDS` (1.5s)
  it finalizes finished runs, processes at most one controller consult, picks one
  dispatchable candidate, and starts it. It catches all exceptions so it never dies.
- **Single-flight per provider** — at most one run per provider at a time.
  `RUNNER.running_for_provider` is the gate, checked in
  [queue_service._pick_candidate](../backend/agentflow/queue_service.py) (skips a provider
  that's busy), in [task_service.run_step](../backend/agentflow/task_service.py) (returns
  `provider_busy`), and in [chat_service](../backend/agentflow/chat_service.py). Intra-task
  step order is preserved: a task with an active (running/blocked/awaiting) item won't have a
  later step dispatched.
- **ProcessRunner run records** — [process_runner.py](../backend/agentflow/process_runner.py)
  keeps in-memory `RunRecord`s (`RUNNER.runs`, bounded to ~100 finished) and live `Process`
  handles (`RUNNER.procs`). `start()` returns immediately and consumes stdout/stderr in a
  background task, emitting capped, whitespace-aligned deltas (so a secret is never split
  mid-redaction) plus a 10s heartbeat. Children run in their own process group
  (`start_new_session=True`) for clean group-kill; `PORT`/`AGENTFLOW_PORT` are stripped from
  child env so a spawned dev server can't hijack `:8787`. Cancel = SIGTERM the group, then
  SIGKILL after 4s.
- **PTY sessions outlive WebSocket connections** —
  [terminal_service.TerminalSession](../backend/agentflow/terminal_service.py) keys a session
  by `workspace::provider` and keeps it alive across socket connects/disconnects, replaying a
  bounded scrollback buffer to each new client. Output is read non-blocking via the loop's
  `add_reader` and fanned out to per-client `asyncio.Queue`s. Sessions detach
  (`start_new_session=True`); a pidfile + startup sweep reaps groups leaked by a crash.

## 7. Agent run lifecycle

**A task step → subprocess** ([task_service.run_step](../backend/agentflow/task_service.py)):

1. Resolve the step's provider from workspace routing (`STEP_DEFS[step].role` →
   [config.get_workspace_routing](../backend/agentflow/config.py)), unless a queue item
   carries a `providerOverride`.
2. Build the prompt ([prompt_templates](../backend/agentflow/prompt_templates.py)) and the
   command preview. Gates, in order: provider single-flight (`provider_busy`);
   `manual_approval` mode + auto source → `manual_preview`; provider not installed → save the
   intended prompt and mark `provider_missing`; Claude health `red` + unconfirmed →
   `needs_confirmation`.
3. Render argv via [agent_commands.build_argv](../backend/agentflow/agent_commands.py):
   `shlex.split` the template from [config.DEFAULT_COMMAND_TEMPLATES](../backend/agentflow/config.py),
   substitute `{prompt}` as a **single argv element** (never interpolated into a shell) and
   `{model}` → `--model <model>` (or dropped), then resolve `argv[0]` to an absolute path.
4. Write the redacted prompt to `logs/<stamp>-<step>.prompt.txt`; snapshot task files + git
   changes for artifact/code-change detection.
5. [RUNNER.start](../backend/agentflow/process_runner.py) spawns the process
   (`stream_kind="run"`, `workspace=` set so it streams). The step is marked `running`, the
   run is persisted immediately (so a mid-run restart can recover it), and `run.started` is
   appended.
6. On completion the `on_complete` hook classifies the failure kind, records usage, detects
   written artifacts + changed production files, sets the final step state, appends the
   durable run + `run.finished`, and updates `ROUTING_DECISIONS.md`.

**A chat message → subprocess** ([chat_service.send](../backend/agentflow/chat_service.py)):
the controller chat builds a prompt from a workspace summary + transcript, runs the
orchestrator-routed CLI (`stream_kind="controller"`), and on success parses fenced
directives ([chat_directives](../backend/agentflow/chat_directives.py)) to create tasks,
queue steps, or run commands. `send_direct` chats one agent with no directives.
`orchestrator_consult` is the system-initiated turn after a step finishes (the "closed
loop"): the dispatcher enqueues a consult, the controller reviews the result and replies
with a `queue` / `done` / `needs-user` / `run` directive (bounded by `MAX_CONSULTS_PER_TASK`).

**Full sequence** ([task_service.run_full_sequence](../backend/agentflow/task_service.py)):
runs `codex_spec → claude_implement → gemini_qa → codex_review`
([workflow.FULL_SEQUENCE](../backend/agentflow/workflow.py)) sequentially in a background
task, with a free local git pre-check first, Budget-Saver spec-skip for small goals, and a
hard pause before `claude_implement` when Claude is `red`.

**State machine** ([transitions.py](../backend/agentflow/transitions.py)): explicit
from→to tables for `task`, `step`, `queue`, and `run`. `is_valid(kind, frm, to)` is the
validated chokepoint used by the durable/queue/step mutators. It is deliberately
**permissive**: a no-op or any transition involving an unknown status is allowed; only a
*known→known* transition outside the table is rejected (logged, not raised — the queue is
never wedged), so legacy `task.json` values keep working.

## 8. Trust boundaries

(See [SECURITY.md](SECURITY.md) for depth; brief here.)

- **Localhost-only binding** — backend serves on `127.0.0.1` only
  ([__main__.py](../backend/agentflow/__main__.py)).
- **Workspace confinement** — [config.set_workspace](../backend/agentflow/config.py) refuses
  the filesystem root and `$HOME`; [workspace.py](../backend/agentflow/workspace.py) and
  [task_service.read_task_file](../backend/agentflow/task_service.py) resolve paths with
  `is_relative_to` and refuse escapes; `.env` files are never previewed/written; the SPA
  static handler confines to `dist`. Spawned agents run with `cwd = workspace`.
- **Command policy** — [policy_service.classify_action](../backend/agentflow/policy_service.py)
  classifies every controller-run command before execution: `deny` (shell operators,
  `..` traversal, absolute paths outside workspace, blocked binaries, inline interpreters,
  env-var prefixes, `rm -rf /`), `require_approval` (installs, `git push/pull`, `gh`, deploys
  → durable approval via [state_store.create_approval](../backend/agentflow/state_store.py)),
  or `allow`. Commands are `shlex`-parsed and exec'd directly — never through a shell.
- **Redaction** — [redaction.redact](../backend/agentflow/redaction.py) masks tokens, keys,
  `KEY=value` secrets, and URL credentials. It runs in the event bus and process runner
  before anything is persisted or broadcast; the browser never redacts.
- **WebSocket origin allowlist** — the PTY WebSocket
  ([routes_terminals.py](../backend/agentflow/api/routes_terminals.py)) rejects browser
  origins outside `localhost:5180` / `localhost:8787` (a missing Origin, e.g. native/test
  clients, is allowed), so a malicious page can't drive a real shell. HTTP routes share the
  same allowlist via [origins.py](../backend/agentflow/origins.py) — CORS plus an
  `OriginGuard` CSRF check on mutating methods, allowing `:5180`/`:8787` origins.
- **Preview confinement** — preview URLs and the reachability check are restricted to
  `localhost` / `127.0.0.1` ([routes_preview.py](../backend/agentflow/api/routes_preview.py)).
