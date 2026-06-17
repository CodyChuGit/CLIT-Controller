# Operations Guide — CLIT Controller IDE (AgentComposer)

CLIT Controller IDE ("Command Line Interface Terminal Controller") is a **local-first,
macOS-oriented developer tool**: a FastAPI backend plus a React/Vite frontend that
orchestrates CLI coding agents (Codex, Claude Code, Antigravity). It is meant to be run
by a single developer on their own machine. It is **not** a multi-user server, and there
is no container, orchestrator, reverse proxy, database, or remote deployment.

This guide is operational: how to run it, where its state lives, what happens on
restart/shutdown, and how to troubleshoot and reset.

---

## 1. Runtime model

A single local Python process serves everything.

- The backend is launched as `python -m agentflow`. See
  [`backend/agentflow/__main__.py`](../backend/agentflow/__main__.py): it binds
  **`127.0.0.1` only** (loopback — not reachable from other machines) on a port read
  from `AGENTFLOW_PORT` (default **`8787`**), and runs Uvicorn on
  `agentflow.app:app`.
- The FastAPI app is defined in [`backend/agentflow/app.py`](../backend/agentflow/app.py).
  It mounts the API routers under `/api/*` and, when a built frontend exists, serves it
  from the same port (single-port mode).
- There is **no container or orchestrator**. The process is the whole runtime.
- It is **macOS-targeted**: launcher and bundle scripts use `open` / `open -a`, build
  `.app` bundles, and use `sips`/`iconutil` for icons. It can run the bare backend on
  any POSIX system, but the app-mode launchers and `.app` wrappers assume macOS.

### Environment knobs

| Variable | Purpose | Default | Defined in |
|---|---|---|---|
| `AGENTFLOW_PORT` | Backend (and single-port app) TCP port | `8787` | [`__main__.py`](../backend/agentflow/__main__.py) |
| `SHELL` | Shell used for PTY terminal sessions | `/bin/bash` | [`terminal_service.py`](../backend/agentflow/terminal_service.py) (`_shell()`) |

PTY child processes also get `TERM=xterm-256color`, `LANG`, `COLORTERM`, and a
`PATH` prepended with `~/.local/bin` and `~/bin` so user-installed CLIs resolve
(see `_child_env()` and `EXTRA_BIN_DIRS` in
[`provider_probe.py`](../backend/agentflow/provider_probe.py)).

> Security note: the backend trusts loopback. It does no auth. Do not expose
> `127.0.0.1:8787` to a network (e.g. via a tunnel or proxy) — it can run agent CLIs
> and read/write inside the selected workspace.

---

## 2. Run paths

There are three supported ways to run the app. The first two are the real ones; the
app-mode launchers are convenience shells on top of single-port mode.

### A. Development (canonical) — `scripts/dev.sh`

[`scripts/dev.sh`](../scripts/dev.sh) runs the backend and the Vite dev server together:

- Backend on **`:8787`** (`.venv/bin/python -m agentflow`).
- Vite dev server on **`:5180`** with hot reload — **open this URL while developing.**
- Vite proxies `/api` (including the terminal WebSockets, `ws: true`) to
  `127.0.0.1:8787`; see [`frontend/vite.config.ts`](../frontend/vite.config.ts).
- On start it **frees both ports first** (`lsof` → SIGTERM, escalating to SIGKILL) so
  duplicate backends / Vite servers can't pile up, and on exit it stops the backend
  gracefully and frees `:5180`.

> Note: the PWA service worker does **not** register on the dev server — install the
> PWA from single-port mode (path B), not from `:5180`.

### B. Single-port production (what you ship/install)

Build the frontend, then run the backend; the backend serves `frontend/dist` from the
same port, so the whole app is one URL:

```bash
npm --prefix frontend run build
AGENTFLOW_PORT=8787 .venv/bin/python -m agentflow
# open http://localhost:8787
```

In [`app.py`](../backend/agentflow/app.py), if `frontend/dist/index.html` exists the app
mounts `/assets` and serves the SPA shell for all other paths (with a `..`/path-traversal
guard confining reads to `dist`). If `dist` is absent, only the API is served.

### C. macOS `.app` / Chrome "app mode" (optional convenience)

These start the backend (single-port) and open Chrome in `--app` mode (own window, no
tabs/address bar). The design intent is in
[`docs/pwa-chrome-app-mode.md`](./pwa-chrome-app-mode.md).

**Source of truth (preferred):**
- [`scripts/app-mode.sh`](../scripts/app-mode.sh) — the canonical launcher. Honors
  `AGENTFLOW_PORT`, only manages the backend **it** starts (leaves an already-healthy
  backend alone), polls `GET /api/health`, writes logs/PID under
  `/tmp/clitc-controller/` (override with `CLITC_RUNTIME_DIR`), builds the frontend if
  missing, and never runs installers/git/remote commands. Falls back to a plain message
  if Chrome is absent.
- [`scripts/create-macos-app-mode.sh`](../scripts/create-macos-app-mode.sh) — generates
  a thin `dist/CLIT Controller IDE.app` that just `exec`s `app-mode.sh`. All logic stays
  in the script.

**Redundant / older overlapping scripts (known wart — not deleting):**
- [`scripts/app.sh`](../scripts/app.sh) — an earlier launcher. Hardcodes `:8787`, uses a
  dedicated Chrome profile (`~/.clitcontroller-chrome`), runs Chrome in the foreground,
  and waits on the root URL rather than `/api/health`.
- [`scripts/make-app.sh`](../scripts/make-app.sh) — an earlier `.app` generator that
  builds `CLIT Controller.app` (note: different bundle name/identifier) wrapping
  `app.sh`.

`app.sh`+`make-app.sh` and `app-mode.sh`+`create-macos-app-mode.sh` are two parallel
implementations of the same feature. Prefer the `app-mode` pair. The duplication is a
documented wart; do not delete either pair without consolidating.

---

## 3. First-time setup

Run the one-time installer: [`scripts/install.sh`](../scripts/install.sh). It:

1. Finds a **Python ≥ 3.11** (tries `$PYTHON`, then `python3.13/3.12/3.11/3`; errors out
   if none qualifies — `requires-python = ">=3.11"` in
   [`pyproject.toml`](../pyproject.toml)).
2. Creates `.venv` if missing.
3. `pip install -e ".[dev]"` (FastAPI, Uvicorn, Pydantic, pytest).
4. `npm install` in `frontend/` (with an isolated-cache retry if `~/.npm` permissions
   fail).

```bash
./scripts/install.sh
```

> On this machine the system `python3` is 3.9; the venv must be built from a 3.11+
> interpreter (e.g. `brew install python@3.12`). The installer enforces this.

External agent CLIs (Codex, Claude Code, Antigravity) are **not** installed by this
script — install them separately (see README) or use the in-app Agents view. The app
never stores provider keys/tokens; each CLI keeps its own login.

---

## 4. Build

```bash
cd frontend && npm run build
```

This runs `tsc && vite build` (see [`frontend/package.json`](../frontend/package.json))
and emits the production bundle to **`frontend/dist/`**, which the backend serves in
single-port mode. `paths.frontend_dist()` in
[`backend/agentflow/paths.py`](../backend/agentflow/paths.py) resolves it relative to the
repo root.

---

## 5. State & data locations

All state is **plaintext JSON**, written atomically (tmp file + `os.replace`; see
`write_json` in [`config.py`](../backend/agentflow/config.py)). There is no database.

### Global — `~/.agentflow/` (per machine/user)

Defined in [`backend/agentflow/paths.py`](../backend/agentflow/paths.py):

| Path | Contents |
|---|---|
| `~/.agentflow/config.json` | Global config: `currentWorkspace`, `routing`, `commandTemplates`, `models` |
| `~/.agentflow/providers.json` | Cached provider/CLI probe results |
| `~/.agentflow/run/terminals/<pid>.session` | One pidfile per live PTY session, used to reap orphans on restart |
| `~/.agentflow/bin/` | Login helper scripts |

### Per-workspace — `<workspace>/.agentflow/`

Created when you select a workspace (`ensure_workspace` in
[`config.py`](../backend/agentflow/config.py)). A self-`.gitignore` (`*`) is written so
this directory stays out of the user's repo.

| File / dir | Contents | Defined in |
|---|---|---|
| `config.json` | Workspace path + routing | [`config.py`](../backend/agentflow/config.py) |
| `usage.json` | Approximate provider usage tracking | [`usage_service.py`](../backend/agentflow/usage_service.py) |
| `tasks/` | Per-task folders (markdown handoffs, `task.json`, `logs/`) | [`paths.py`](../backend/agentflow/paths.py), `task_service` |
| `events.json` | Append-only timeline (bounded to 2000 events) | [`state_store.py`](../backend/agentflow/state_store.py) |
| `runs.json` | Durable run ledger (bounded to 200; never drops a `running` run) | [`state_store.py`](../backend/agentflow/state_store.py) |
| `approvals.json` | Pending/resolved approvals for risky actions | [`state_store.py`](../backend/agentflow/state_store.py) |
| `queue.json` | Step queue (survives restart) | [`queue_service.py`](../backend/agentflow/queue_service.py) |
| `chat.json` | Chat history | [`chat_service.py`](../backend/agentflow/chat_service.py) |

> Workspace guardrails: `set_workspace` refuses the filesystem root and `$HOME` as a
> workspace, because read/write/git/command surfaces are confined to the chosen folder.

---

## 6. Startup recovery & graceful shutdown

Handled by the lifespan context manager in
[`backend/agentflow/app.py`](../backend/agentflow/app.py).

### On (re)start

1. **Durable-state recovery** — `state_store.recover_workspace(ws)`
   ([`state_store.py`](../backend/agentflow/state_store.py)) runs before the dispatcher.
   A restart can't keep driving a process the previous interpreter spawned, so any state
   left `running` is settled truthfully and idempotently:
   - runs marked `running` → `failed` with `failureKind: backend_restart`;
   - their queue items → `failed` (interrupted), and later queued steps of the same task
     → `blocked`;
   - task steps claiming `running` with no live run → `failed`.
   A `system` log entry summarizes what was settled.
2. **Orphan terminal sweep** — `sweep_orphaned_sessions()`
   ([`terminal_service.py`](../backend/agentflow/terminal_service.py)) reaps PTY process
   groups leaked by a prior backend that died without its shutdown hook (crash/SIGKILL).
   PTY sessions detach (`start_new_session=True`), so each drops a pidfile under
   `~/.agentflow/run/terminals/`. The sweep `SIGKILL`s only recorded pids that still look
   like a detached shell we spawned (no controlling tty + matching shell name), guarding
   against PID reuse.
3. The **dispatcher loop** starts (`queue_service.dispatcher_loop()`), cueing queued
   steps to agents for the life of the process.

### On shutdown

The lifespan teardown:

1. **cancels the dispatcher** task, then
2. **`TERMINALS.shutdown()`** — terminates every PTY session (SIGTERM to the process
   group, then SIGKILL backstop), clearing their pidfiles.

### ⚠ Known operational gap — orphaned agent subprocesses

The lifespan shutdown does **not** call `RUNNER.cancel_all()`. In-flight **agent**
subprocesses (the non-PTY runs tracked in `ProcessRunner.procs`, started via
`asyncio.create_subprocess_exec` in
[`process_runner.py`](../backend/agentflow/process_runner.py)) are therefore **not
terminated on shutdown** and can be left orphaned. `cancel_all()` exists and is wired to
a task-service stop action and `cancel()` to chat/preview, but neither is invoked from
[`app.py`](../backend/agentflow/app.py)'s teardown.

Mitigations today: the next startup's `recover_workspace` settles their *records* as
`backend_restart` (so the UI isn't stuck), but the OS processes themselves may linger.
Unlike PTY sessions, these non-PTY runs leave **no pidfile**, so the startup sweep does
not reap them. This is being addressed in the hardening pass; until then, after an abrupt
stop, check for stray agent processes (e.g. `pgrep -fl 'codex|claude|agy'`) and kill any
that don't belong to a live session.

---

## 7. Health check & API docs

- **Health:** `GET /api/health` → `{ "ok": true, "app": "CLIT Controller IDE", ... }`
  ([`app.py`](../backend/agentflow/app.py)). The `app-mode.sh` launcher polls this for
  readiness.
- **Interactive API docs:** `http://localhost:8787/docs` (FastAPI Swagger UI).

```bash
curl -fsS http://localhost:8787/api/health
```

---

## 8. Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| **Port already in use** | `dev.sh` auto-frees `:8787`/`:5180` (`lsof` → SIGTERM → SIGKILL). For other launchers, find and kill the holder: `lsof -nP -tiTCP:8787 -sTCP:LISTEN` then `kill <pid>`. Or run on another port: `AGENTFLOW_PORT=9000 …`. |
| **Provider CLI not installed** | Terminal shows e.g. agent not found; Agents view shows setup status. Install the CLI (README) or use the in-app install/setup actions. The backend probes user-bin dirs (`~/.local/bin`, `~/bin`) plus your `PATH`. |
| **Stale / hung terminal session** | Each PTY auto-cleans on exit and prints `[session ended — reconnect to restart]`; reconnecting restarts it. Orphans from a crash are reaped on next startup. To force-clear, restart the backend; if a group truly lingers, kill it via the pidfiles in `~/.agentflow/run/terminals/`. |
| **"No workspace selected" (409)** | No `currentWorkspace` is set. API routes return HTTP **409** ("No workspace selected. Set one on the Projects page.") — see [`api/routes_projects.py`](../backend/agentflow/api/routes_projects.py); the terminal WS shows the same in yellow. Pick a workspace on the Projects/Explorer page. |
| **PWA installed with a blank/old icon** | Remove the installed app and reinstall from `http://localhost:8787` (not the dev server) so Chrome/macOS refreshes the cached icon (README + [`docs/pwa-chrome-app-mode.md`](./pwa-chrome-app-mode.md)). |
| **app-mode launcher reports backend failed to start** | It prints the log path (default `/tmp/clitc-controller/backend.log`) and tails the last lines. Inspect that log. |
| **Frontend not served on `:8787`** | `frontend/dist` is missing — run `npm --prefix frontend run build`. |

---

## 9. Backup & reset

State is just files; there is nothing else to back up.

- **Back up:** copy `~/.agentflow/` (global) and each `<workspace>/.agentflow/` (per
  project).
- **Reset a workspace:** delete `<workspace>/.agentflow/` — it is recreated empty on next
  selection.
- **Reset everything (global):** delete `~/.agentflow/`. This drops the selected
  workspace, routing, provider cache, and login scripts; defaults are re-seeded on next
  run.

No migrations run on delete — empty/missing files recover to defaults.

---

## 10. Rollback

This is a local app with no database and no schema migrations, so rollback is a git +
rebuild operation:

1. `git checkout <previous-commit-or-tag>`
2. If Python deps changed: `./scripts/install.sh` (or `.venv/bin/pip install -e ".[dev]"`).
3. Rebuild the frontend: `npm --prefix frontend run build`.
4. Restart the backend.

JSON state files are forward/backward tolerant (schema-versioned ledgers migrate/repair
their own shape on load — see `_load_doc` in
[`state_store.py`](../backend/agentflow/state_store.py)), but they are **not** explicitly
downgraded. If a rollback crosses an incompatible state change, reset the affected
`.agentflow/` directory (section 9) rather than hand-editing.
