# API

The HTTP + WebSocket + Server-Sent-Events surface of the backend
([`app.py`](../backend/agentflow/app.py) + the routers under
[`backend/agentflow/api/`](../backend/agentflow/api/)).

The **authoritative, always-current** API reference is FastAPI's generated
OpenAPI schema. When the backend is running, browse it at:

- Interactive docs (Swagger UI): <http://127.0.0.1:8787/docs>
- Raw schema: <http://127.0.0.1:8787/openapi.json>

This document is a hand-written orientation map over that schema — it groups the
endpoints by router and explains the conventions (auth, errors, streaming) that
the OpenAPI schema does not spell out. Where the two disagree, the generated
schema wins.

## Base URL & transport

- **Base URL:** `http://127.0.0.1:8787` (backend binds loopback only; port is
  overridable via `AGENTFLOW_PORT`). In dev, the Vite server on `:5180` proxies
  `/api` to the backend ([`frontend/vite.config.ts`](../frontend/vite.config.ts)).
- **Prefix:** every endpoint below lives under `/api`. Non-`/api` paths are the
  SPA shell / static assets when the built frontend is present (single-port mode).
- **Body format:** JSON in, JSON out. Request bodies are validated by Pydantic
  models ([`models.py`](../backend/agentflow/models.py) and a few inline models in
  the route files); a validation failure returns `422` with FastAPI's standard
  error body.
- **Exceptions:** the terminal stream is a **WebSocket** (binary out / JSON
  control in) and `/api/events/stream` is a **Server-Sent Events** stream
  (`text/event-stream`). Both are detailed below.

## Authentication

**None.** This is a single-user, local-first tool that binds loopback only, so
there is no login, token, or API key. The trust boundary is *the loopback
interface plus origin checks*, not authentication. See
[SECURITY.md](SECURITY.md) for the full threat model.

Two origin-based controls stand in for auth:

- **CORS** restricts which browser origins may *read* responses
  (`CORSMiddleware` in [`app.py`](../backend/agentflow/app.py), allow-list from
  [`origins.py`](../backend/agentflow/origins.py)).
- **CSRF Origin guard** (`OriginGuardMiddleware` in
  [`app.py`](../backend/agentflow/app.py)) rejects **mutating** requests
  (`POST`/`PUT`/`PATCH`/`DELETE`) that carry a *foreign* browser `Origin` (or
  `Referer` when `Origin` is absent) with `403 {"detail": "cross-origin request
  rejected"}`. A missing Origin (native clients, `curl`, tests, same-origin GET
  navigations) is allowed. CORS alone does not stop a cross-site request from
  *executing* server-side, which on a no-auth command runner is a CSRF vector;
  this guard closes it. The same allow-list backs the WebSocket origin check.

The allowed origins are exactly the app's own ports:
`http://localhost:5180`, `http://127.0.0.1:5180`, `http://localhost:8787`,
`http://127.0.0.1:8787`.

## Error & status conventions

Two distinct patterns coexist; the second is a known wart, flagged honestly:

1. **HTTP status + `{"detail": "..."}`** (FastAPI `HTTPException`). Used across
   `/api/projects`, `/api/agents`, `/api/tasks`, `/api/usage`, `/api/queue/add`,
   `/api/preview`, and the state router. Common codes:
   - `400` — bad input (invalid path, empty commit message, non-localhost preview
     URL, non-macOS "open folder").
   - `404` — unknown provider, missing task/run/approval/file.
   - `409` — **no workspace selected** (`require_workspace()` in
     [`routes_projects.py`](../backend/agentflow/api/routes_projects.py); most
     workspace-scoped endpoints raise this).
   - `422` — Pydantic request-body validation failure.
   - `403` — cross-origin mutating request (the CSRF guard above).

2. **`200 OK` with a status string in the JSON body** — flagged. Several
   `/api/chat` and `/api/preview` endpoints, plus
   `/api/approvals/{id}/approve|reject`, always return `200` and signal the real
   outcome inside the body, e.g. `{"status": "error", "message": "..."}`,
   `{"status": "already_running", ...}`, `{"status": "started", ...}`,
   `{"status": "approved" | "rejected" | "pending", ...}`. Clients must inspect
   the `status` field rather than relying on the HTTP code for these. This is
   inconsistent with pattern (1) and is documented here so consumers do not treat
   a `200` as unconditional success.

There is **no pagination** (list endpoints return full collections; the only
bounded reads are `?cursor=`/`?limit=` on the event ledger) and **no rate
limiting** (loopback, single user).

## Endpoint inventory

`Auth` is "none" for every endpoint (see above); the column instead notes the
**CSRF Origin guard** ("guard" = mutating, subject to `OriginGuardMiddleware`)
and `require_workspace` ("ws" = returns `409` if no workspace is selected).
`Status` is the success status; error statuses follow the conventions above.

### `/api/projects` — workspace, files, git, settings
[`routes_projects.py`](../backend/agentflow/api/routes_projects.py)

| Method | Path | Purpose | Auth | Request | Response | Status |
|--------|------|---------|------|---------|----------|--------|
| GET  | `/api/projects/current` | Current workspace + routing (or `{workspacePath: null}`) | none | — | `{workspacePath,name,agentflowDir,routing}` | 200 |
| POST | `/api/projects/workspace` | Select a workspace, run recovery | guard | `{path}` | `{ok,workspacePath,routing}` | 200 / 400 |
| GET  | `/api/projects/tree` | Scan workspace file tree | ws | — | tree JSON | 200 / 409 |
| GET  | `/api/projects/file` | Read a text file (confined to workspace) | ws | `?path=` | `{path,content,size,...}` | 200 / 400 / 404 / 409 |
| POST | `/api/projects/file` | Write a text file | guard, ws | `{path,content}` | `{size,...}` | 200 / 400 / 404 / 409 |
| GET  | `/api/projects/git` | Git summary (branch, ahead/behind, dirty) | ws | — | git info | 200 / 409 |
| GET  | `/api/projects/git/diff` | Full working-tree diff | ws | — | diff JSON | 200 / 409 |
| GET  | `/api/projects/git/status` | Per-file status list | ws | — | status JSON | 200 / 409 |
| GET  | `/api/projects/git/file-diff` | Diff for one file | ws | `?path=&staged=` | diff JSON | 200 / 409 |
| POST | `/api/projects/git/stage` | Stage a path (or all) | guard, ws | `{path?}` | result | 200 / 409 |
| POST | `/api/projects/git/unstage` | Unstage a path (required) | guard, ws | `{path}` | result | 200 / 400 / 409 |
| POST | `/api/projects/git/commit` | Commit staged changes | guard, ws | `{message}` | `{ok,output,...}` | 200 / 409 |
| POST | `/api/projects/open-folder` | Reveal workspace in Finder (macOS only) | guard, ws | — | `{ok}` | 200 / 400 / 409 |
| GET  | `/api/projects/settings` | Routing, command templates, models, headroom, paths | none | — | settings JSON | 200 |
| POST | `/api/projects/settings` | Update settings; returns full settings | guard | `{routing?,commandTemplates?,models?,headroom?}` | settings JSON | 200 |

### `/api/agents` — CLI detection, login, model config
[`routes_agents.py`](../backend/agentflow/api/routes_agents.py)

| Method | Path | Purpose | Auth | Request | Response | Status |
|--------|------|---------|------|---------|----------|--------|
| GET  | `/api/agents` | List provider cards (install + usage health + model) | none | — | `[provider,...]` | 200 |
| POST | `/api/agents/check` | Re-probe one provider | guard | `{id}` | provider card | 200 / 404 |
| POST | `/api/agents/check-all` | Re-probe all providers | guard | — | `[provider,...]` | 200 |
| POST | `/api/agents/login` | Launch a provider's login/auth flow | guard | `{id}` | result | 200 / 404 |
| POST | `/api/agents/install` | Install a provider's CLI | guard | `{id}` | result | 200 / 404 |
| POST | `/api/agents/model` | Set the model for a model-configurable agent | guard | `{id,model}` | `{ok,id,model}` | 200 / 404 |

### `/api/tasks` — task creation & step execution
[`routes_tasks.py`](../backend/agentflow/api/routes_tasks.py)

| Method | Path | Purpose | Auth | Request | Response | Status |
|--------|------|---------|------|---------|----------|--------|
| GET  | `/api/tasks` | List tasks in the workspace | ws | — | `[task,...]` | 200 / 409 |
| POST | `/api/tasks` | Create a task (title + goal) | guard, ws | `{title,goal}` | task | 200 / 409 |
| POST | `/api/tasks/stop` | Stop a running task run | guard | `{runId?}` | result | 200 |
| GET  | `/api/tasks/{task_id}` | Task detail | ws | — | task detail | 200 / 404 / 409 |
| POST | `/api/tasks/{task_id}/run/{step}` | Run one step (PM/engineer/QA) | guard, ws | `{confirm}` | run result | 200 / 400 / 404 / 409 |
| POST | `/api/tasks/{task_id}/run-full` | Run the full step sequence | guard, ws | `{confirm}` | run result | 200 / 404 / 409 |
| POST | `/api/tasks/{task_id}/open-folder` | Reveal task folder in Finder (macOS) | guard, ws | — | `{ok}` | 200 / 400 / 404 / 409 |
| GET  | `/api/tasks/{task_id}/exchanges` | Per-step prompt/response exchanges | ws | — | `{steps}` | 200 / 409 |
| GET  | `/api/tasks/{task_id}/logs` | Task log files + run records | ws | — | `{files,runs}` | 200 / 409 |
| GET  | `/api/tasks/{task_id}/file` | Read a file inside the task folder | ws | `?name=` | file JSON | 200 / 404 / 409 |

### `/api/usage` — traffic control, health, routing
[`routes_usage.py`](../backend/agentflow/api/routes_usage.py)

| Method | Path | Purpose | Auth | Request | Response | Status |
|--------|------|---------|------|---------|----------|--------|
| GET  | `/api/usage` | Workspace usage + orchestration mode | ws | — | usage JSON | 200 / 409 |
| POST | `/api/usage/mode` | Set orchestration mode | guard, ws | `{mode}` | usage JSON | 200 / 409 |
| POST | `/api/usage/provider-health` | Override a provider's usage health | guard, ws | `{provider,health}` | usage JSON | 200 / 409 |
| POST | `/api/usage/provider-limit` | Set a provider call/window limit | guard, ws | `{provider,limitCalls?,windowHours?}` | usage JSON | 200 / 409 |
| GET  | `/api/usage/live` | Best-effort live usage (optionally forced) | none | `?force=` | live usage | 200 |
| GET  | `/api/usage/recommendations` | Routing recommendation for current diff | ws | — | recommendation | 200 / 409 |

### `/api/logs` — global activity log + live runs
[`routes_logs.py`](../backend/agentflow/api/routes_logs.py)

| Method | Path | Purpose | Auth | Request | Response | Status |
|--------|------|---------|------|---------|----------|--------|
| GET  | `/api/logs` | Redacted activity log + currently running runs (tail) | none | — | `{entries,running}` | 200 |
| POST | `/api/logs/clear-view` | Clear the in-memory log view | guard | — | `{ok}` | 200 |

### `/api/terminals` — live CLI terminals (HTTP control + WebSocket)
[`routes_terminals.py`](../backend/agentflow/api/routes_terminals.py)

| Method | Path | Purpose | Auth | Request | Response | Status |
|--------|------|---------|------|---------|----------|--------|
| GET  | `/api/terminals/status` | Which agent CLIs are installed | none | — | `{providers,installed}` | 200 |
| POST | `/api/terminals/{provider}/kill` | Kill a provider's PTY session | guard | — | `{ok}` | 200 |
| WS   | `/api/terminals/{provider}/ws` | Bidirectional PTY terminal | Origin allow-list | JSON control frames | binary output frames | see below |

### `/api/chat` — chat with the traffic-control model
[`routes_chat.py`](../backend/agentflow/api/routes_chat.py) — note: `/send`,
`/direct`, `/stop` use the **`200` + `status` string** body pattern.

| Method | Path | Purpose | Auth | Request | Response | Status |
|--------|------|---------|------|---------|----------|--------|
| GET  | `/api/chat` | Current chat state (transcript) | ws | — | chat state | 200 / 409 |
| POST | `/api/chat/send` | Send a message to the orchestrator | guard, ws | `{message,provider?}` | `{status,...}` | 200 / 409 |
| POST | `/api/chat/direct` | Send directly to a provider | guard, ws | `{message,provider}` | `{status,...}` | 200 / 409 |
| POST | `/api/chat/stop` | Stop a channel's in-flight reply | guard, ws | `{channel?}` | `{status,...}` | 200 / 409 |
| POST | `/api/chat/clear` | Clear a channel's transcript | guard, ws | `{channel?}` | `{ok}` | 200 / 409 |

### `/api/queue` — execution queue
[`routes_queue.py`](../backend/agentflow/api/routes_queue.py) — inline request
models in the route file. Most actions take `{itemId}`.

| Method | Path | Purpose | Auth | Request | Response | Status |
|--------|------|---------|------|---------|----------|--------|
| GET  | `/api/queue` | Current queue state | ws | — | queue state | 200 / 409 |
| POST | `/api/queue/add` | Enqueue task steps | guard, ws | `{taskId,steps[]}` | queue/add result | 200 / 400 / 404 / 409 |
| POST | `/api/queue/approve` | Approve & dispatch a queued item | guard, ws | `{itemId}` | `{...,queue}` | 200 / 409 |
| POST | `/api/queue/remove` | Remove an item | guard, ws | `{itemId}` | result | 200 / 409 |
| POST | `/api/queue/clear` | Clear the queue | guard, ws | — | result | 200 / 409 |
| POST | `/api/queue/retry` | Re-queue a failed item | guard, ws | `{itemId}` | result | 200 / 409 |
| POST | `/api/queue/skip` | Skip an item | guard, ws | `{itemId}` | result | 200 / 409 |
| POST | `/api/queue/reroute` | Reroute an item to another provider | guard, ws | `{itemId,provider}` | result | 200 / 409 |

### `/api` (state) — events, run ledger, approvals
[`routes_state.py`](../backend/agentflow/api/routes_state.py) — durable state
surface. `/events` and `/events/stream` are the streaming contract (below).

| Method | Path | Purpose | Auth | Request | Response | Status |
|--------|------|---------|------|---------|----------|--------|
| GET  | `/api/events` | Events with `id > cursor` (polling fallback) | ws | `?cursor=&limit=` | `{events,cursor}` | 200 / 409 |
| GET  | `/api/events/stream` | SSE stream of live events (resumable) | ws | `?cursor=` + `Last-Event-ID` | `text/event-stream` | 200 / 409 |
| GET  | `/api/runs/{run_id}` | One run record from the ledger | ws | — | run | 200 / 404 / 409 |
| GET  | `/api/approvals` | List approvals (optionally pending only) | ws | `?pendingOnly=` | `{approvals}` | 200 / 409 |
| POST | `/api/approvals/{id}/approve` | Approve (and execute command approvals) | guard, ws | — | `{status,approval}` | 200 / 404 / 409 |
| POST | `/api/approvals/{id}/reject` | Reject an approval | guard, ws | — | `{status,approval}` | 200 / 404 / 409 |

### `/api/preview` — workspace dev server
[`routes_preview.py`](../backend/agentflow/api/routes_preview.py) — `/start`,
`/stop` use the **`200` + `status` string** body pattern.

| Method | Path | Purpose | Auth | Request | Response | Status |
|--------|------|---------|------|---------|----------|--------|
| GET  | `/api/preview` | Dev-server state (running, command, url, output tail) | ws | — | preview state | 200 / 409 |
| POST | `/api/preview/url` | Set preview URL (localhost only) | guard, ws | `{url}` | preview state | 200 / 400 / 409 |
| GET  | `/api/preview/check` | TCP reachability of the preview URL | ws | — | `{ok,detail?}` | 200 / 409 |
| POST | `/api/preview/start` | Start the dev server | guard, ws | `{command?}` | `{status,...}` | 200 / 400 / 409 |
| POST | `/api/preview/stop` | Stop the dev server | guard, ws | — | `{stopped,...}` | 200 / 409 |

### `/api/health` — liveness
[`app.py`](../backend/agentflow/app.py)

| Method | Path | Purpose | Auth | Request | Response | Status |
|--------|------|---------|------|---------|----------|--------|
| GET  | `/api/health` | Liveness + app identity/version | none | — | `{ok,app,fullName,tagline,version}` | 200 |

## Server-Sent Events: `/api/events/stream`

The live event stream is the primary push channel for timeline events, run
status changes, and **text deltas** from agent output. It is implemented in
[`routes_state.py`](../backend/agentflow/api/routes_state.py) over the in-memory
event bus ([`event_bus.py`](../backend/agentflow/event_bus.py)).

- **Media type:** `text/event-stream` (`Cache-Control: no-cache`,
  `X-Accel-Buffering: no`).
- **Cursor-resumable.** Each frame is `id: <n>\ndata: <json>\n\n`. There is **no
  `event:` line**, so a browser consumes everything via
  `EventSource.onmessage` — the event *type* lives inside the JSON payload
  (`payload.type`), not the SSE event name.
- **Resume on reconnect.** Pass a starting point with `?cursor=<id>`; the browser
  also sends `Last-Event-ID` automatically on reconnect. The server resumes from
  `max(cursor, Last-Event-ID)` so streamed text is never duplicated.
- **Keep-alive.** After ~5s of quiet the server emits a `: ping\n\n` comment.
- **Payload shape** (one JSON object per `data:` frame, see `EventBus.publish`):
  `id`, `type`, `createdAt`/`time`, `workspacePath`, `provider`, `taskId`,
  `runId`, `queueItemId`, `step`, `sequence`, `channel`, `textDelta`,
  `redacted`, `truncated`, `detail`, `data`. All text fields are redacted before
  emission.

Minimal browser consumer:

```js
const es = new EventSource("/api/events/stream?cursor=0");
es.onmessage = (e) => {
  const ev = JSON.parse(e.data);     // dedupe by ev.id; switch on ev.type
  if (ev.textDelta) appendOutput(ev.runId, ev.textDelta);
};
```

### Polling fallback: `/api/events?cursor=`

When SSE is unavailable, poll `GET /api/events?cursor=<lastId>&limit=<n>`
(default `limit=500`). It returns the **same** events (including `textDelta`)
from the same bus, oldest-first, plus the current `cursor`:

```json
{ "events": [ /* event objects, id > cursor */ ], "cursor": 1234 }
```

Advance your cursor to the last `id` you consumed and **dedupe by `id`** (the SSE
and polling paths can overlap on reconnect).

## Terminal WebSocket: `/api/terminals/{provider}/ws`

A bidirectional PTY bridge to a real agent CLI shell
([`routes_terminals.py`](../backend/agentflow/api/routes_terminals.py)). `{provider}`
must be one of the agent provider ids (see `GET /api/terminals/status`).

- **Origin allow-list (CSWSH defense).** WebSocket handshakes bypass CORS, so the
  handler checks the `Origin` header against the shared allow-list
  ([`origins.py`](../backend/agentflow/origins.py)) and closes with code **4403**
  on a foreign origin. A missing Origin (native clients, tests) is allowed. See
  [SECURITY.md](SECURITY.md).
- **Close codes:** `4403` foreign origin; `4404` unknown provider; a clean close
  with a message if no workspace is selected.
- **Output — server → client: raw binary frames.** On connect the server replays
  the session scrollback as a binary snapshot, then streams live PTY bytes. Decode
  and feed straight into an `xterm.js` instance.
- **Input/control — client → server: JSON text frames.** Recognized shapes:
  - `{"type":"input","data":"..."}` — keystrokes / paste.
  - `{"type":"resize","rows":N,"cols":N}` — PTY resize.
  - `{"type":"kill"}` — terminate the session and close.
  - A raw binary frame, or non-JSON text, is written to the PTY verbatim.
- Sessions are shared per `(workspace, provider)`: reconnecting reattaches to the
  same shell and replays its scrollback. `POST /api/terminals/{provider}/kill`
  ends a session synchronously so the next connect starts fresh.

## Related docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — how the routers, services, event bus, and
  state store fit together.
- [SECURITY.md](SECURITY.md) — full threat model behind the no-auth / Origin-guard
  design.
- [OPERATIONS.md](OPERATIONS.md) — running the backend, ports, environment.
