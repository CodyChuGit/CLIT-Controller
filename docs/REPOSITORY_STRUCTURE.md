# Repository Structure

A curated map of the **CLIT Controller IDE / AgentComposer** repo — what each
important directory is for, what belongs in it (and what doesn't), where the
entry points are, and how neighbouring areas relate. This is a guide, not a full
file dump: routine, self-explanatory files are summarised rather than listed.

For deeper material, this doc **links** rather than repeats:

- Product model & the five pillars → [docs/PILLARS.md](PILLARS.md)
- Runtime architecture, data flow, state ledgers → [docs/ARCHITECTURE.md](ARCHITECTURE.md)
- Running, ports, recovery, processes → [docs/OPERATIONS.md](OPERATIONS.md)
- Threat model, loopback-only, CSRF/CORS/WS origin → [docs/SECURITY.md](SECURITY.md)
- Coding conventions, lint/type/test gates → [docs/ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md)
- Audit findings & remediation → [docs/audit/INITIAL_AUDIT.md](audit/INITIAL_AUDIT.md), [docs/audit/FINAL_REPORT.md](audit/FINAL_REPORT.md)
- Decisions → [docs/adr/0001-auto-run-policy-allowlist.md](adr/0001-auto-run-policy-allowlist.md)

> Note: the Python package directory is named `agentflow` (the project's prior
> name); the product is "CLIT Controller IDE / AgentComposer". Treat the two as
> the same thing.

---

## Top-level layout

```
AgentComposer/
├── backend/              # Python: FastAPI app + agentflow package + tests
│   ├── agentflow/        #   the application package (entry: python -m agentflow)
│   └── tests/            #   pytest suite (hermetic, ~/.agentflow redirected)
├── frontend/             # React 18 + Vite 5 + Tailwind + xterm SPA
│   ├── src/              #   application source
│   ├── public/           #   static assets copied verbatim (PWA manifest, sw, icons)
│   └── dist/             #   BUILD OUTPUT — gitignored
├── scripts/              # setup / dev / launcher / proxy shell scripts
├── docs/                 # design + operations + audit + ADRs (this file lives here)
├── dist/                 # GENERATED macOS .app wrapper — gitignored (/dist)
├── dist-app/             # GENERATED macOS .app bundle — gitignored
├── Makefile              # the one command surface (setup|dev|format|lint|typecheck|test|build|verify)
├── pyproject.toml        # backend package, ruff, mypy, pytest, coverage config
├── requirements.lock     # pinned backend deps (regenerate with `make lock`)
├── .env.example          # documented env vars (AGENTFLOW_PORT, SHELL, headroom.*)
├── .github/workflows/    # CI (ci.yml) — mirrors `make verify`
├── README.md             # quick start
└── DESIGN.md, NEXT_STEPS.md   # narrative design notes (not normative)
```

**Generated / gitignored (never edit by hand, never commit):** `.venv/`,
`__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`,
`.coverage`, `htmlcov/`, `node_modules/`, `frontend/dist/`, `frontend/coverage/`,
`dist-app/`, `/dist/`, `.DS_Store` (see [.gitignore](../.gitignore)). The
`.DS_Store` files committed under some dirs are macOS noise and not meaningful.

---

## `backend/agentflow/` — the application package

The FastAPI app and all server-side logic. **Entry point:**
[`__main__.py`](../backend/agentflow/__main__.py) (`python -m agentflow`) boots
uvicorn on `127.0.0.1:${AGENTFLOW_PORT:-8787}`; the ASGI app is built in
[`app.py`](../backend/agentflow/app.py) (`create_app()` → `app`), which wires
middleware, mounts routers under `/api/*`, exposes `/api/health`, and — when
`frontend/dist` exists — serves the built SPA (single-port mode).

**Layering (high level):** HTTP/WS routers in `api/` are thin; they call
*service* modules here, which read/write durable JSON state and spawn
subprocesses. Cross-cutting concerns (origins, redaction, contracts, paths) are
small standalone modules. No database — see [docs/ARCHITECTURE.md](ARCHITECTURE.md).

| File | Role |
| --- | --- |
| [`app.py`](../backend/agentflow/app.py) | FastAPI factory: `OriginGuardMiddleware` (CSRF), CORS, router registration, SPA static mount, lifespan (startup recovery + orphan reaping, dispatcher loop, shutdown cancel-all). |
| [`__main__.py`](../backend/agentflow/__main__.py) | CLI entry; reads `AGENTFLOW_PORT`, runs uvicorn. |
| [`paths.py`](../backend/agentflow/paths.py) | **Single source of truth for every filesystem location** (global `~/.agentflow/*`, per-workspace `.agentflow/*`, `frontend/dist`). New code that needs a path adds a helper here — do not hardcode paths elsewhere. |
| [`config.py`](../backend/agentflow/config.py) | Global + per-workspace config load/save; current-workspace selection. |
| [`models.py`](../backend/agentflow/models.py) | Pydantic **request** models for the API (input shapes). |
| [`contracts.py`](../backend/agentflow/contracts.py) | **Pillar 5** deterministic, versioned output contracts (directives, summaries, results, handoffs) + safe `validate()`. The typed semantic layer between events and the UI. |
| [`state_store.py`](../backend/agentflow/state_store.py) | Durable, schema-versioned ledgers under `<workspace>/.agentflow/`: `events.json` (append-only timeline), `runs.json`, `approvals.json`; atomic writes + startup recovery so nothing stays stuck `running`. |
| [`event_bus.py`](../backend/agentflow/event_bus.py) | In-process, workspace-scoped event bus feeding `/api/events` (poll) and `/api/events/stream` (SSE); bounded ring buffer, cursor-resumable. |
| [`process_runner.py`](../backend/agentflow/process_runner.py) | Real subprocess runner: spawn agent CLIs, capture+redact output, cancel process groups, write task logs (`RUNNER` singleton). |
| [`terminal_service.py`](../backend/agentflow/terminal_service.py) | Real PTY-backed terminal sessions (`TERMINALS`): interactive shell per pane, raw output over WS, scrollback replay, sessions outlive a single connection, orphan sweeping. |
| [`task_service.py`](../backend/agentflow/task_service.py) | Tasks: folder/markdown handoff files, step execution, full sequence. |
| [`queue_service.py`](../backend/agentflow/queue_service.py) | Execution queue (`queue.json`) + `dispatcher_loop()`; one step per agent at a time, order preserved. |
| [`chat_service.py`](../backend/agentflow/chat_service.py) | Persistent chat with the traffic-control / controller model, run via the user's own CLI agents. |
| [`chat_directives.py`](../backend/agentflow/chat_directives.py) | Parses controller fenced directive blocks (` ```agentflow-task/queue/run/done/needs-user ```), strips them from prose, bridges to typed `contracts`. |
| [`workflow.py`](../backend/agentflow/workflow.py) | Workflow step definitions: step→role/label map, per-step read/write I/O contract, `FULL_SEQUENCE`. |
| [`agent_commands.py`](../backend/agentflow/agent_commands.py) | Turns a provider command template into executable argv (`{model}`/`{prompt}` substitution, executable resolution); provider-busy result helper. |
| [`prompt_templates.py`](../backend/agentflow/prompt_templates.py) | All agent prompt templates (each prefixed with the budget context header) + task file names. |
| [`routing_service.py`](../backend/agentflow/routing_service.py) | Budget-aware routing recommendations; writes `ROUTING_DECISIONS.md`. |
| [`policy_service.py`](../backend/agentflow/policy_service.py) | Classifies a command/action `allow` / `require_approval` / `deny` *before* it reaches the runner (see [ADR-0001](adr/0001-auto-run-policy-allowlist.md)). |
| [`transitions.py`](../backend/agentflow/transitions.py) | Explicit state machines (task/step/queue/run) so invalid transitions are detectable. |
| [`provider_probe.py`](../backend/agentflow/provider_probe.py) | Detect installed CLIs (git, gh, codex, antigravity/`agy`, claude, ollama, omlx); resolve executables. |
| [`usage_service.py`](../backend/agentflow/usage_service.py) | Approximate provider usage tracking in `<workspace>/.agentflow/usage.json`. |
| [`headroom_service.py`](../backend/agentflow/headroom_service.py) | **Pillar 1** optional, fail-open Headroom token-saving proxy integration (injects base-URL env for claude/codex when enabled + reachable). |
| [`origins.py`](../backend/agentflow/origins.py) | Allowed local origins — the single list shared by CORS, the CSRF middleware, and the WebSocket origin check. |
| [`redaction.py`](../backend/agentflow/redaction.py) | Redact secret-looking values from logs and command previews. |
| [`git_service.py`](../backend/agentflow/git_service.py) | Local git: read-only status/diff plus explicit, user-triggered stage/commit. |
| [`workspace.py`](../backend/agentflow/workspace.py) | Workspace file-tree scanning + safe text-file reading. |

**Belongs here:** server logic, durable-state access, subprocess orchestration,
domain rules. **Does NOT belong here:** HTTP routing details (→ `api/`), any
secret material, or UI concerns. New shared filesystem paths → add to `paths.py`;
new validated output shapes → add a versioned contract in `contracts.py`.

---

## `backend/agentflow/api/` — HTTP & WebSocket routers

One module per resource, each a thin FastAPI `APIRouter`. They parse/validate
requests (using `models.py`), delegate to service modules, and shape responses.
Registered in `app.py` under the prefixes shown.

| File | Prefix | Surface |
| --- | --- | --- |
| [`routes_projects.py`](../backend/agentflow/api/routes_projects.py) | `/api/projects` | Workspace selection, file tree, file read, git info, settings. |
| [`routes_agents.py`](../backend/agentflow/api/routes_agents.py) | `/api/agents` | CLI detection, version checks, login/setup launch. |
| [`routes_tasks.py`](../backend/agentflow/api/routes_tasks.py) | `/api/tasks` | Task create, step exec, full sequence, logs, stop, open folder. |
| [`routes_usage.py`](../backend/agentflow/api/routes_usage.py) | `/api/usage` | Traffic-control mode, provider health, routing recommendations. |
| [`routes_logs.py`](../backend/agentflow/api/routes_logs.py) | `/api/logs` | Global redacted activity log + live run output. |
| [`routes_terminals.py`](../backend/agentflow/api/routes_terminals.py) | `/api/terminals` | **WebSocket** PTY terminals: raw binary output (server→client), JSON control frames (input/resize/kill). |
| [`routes_chat.py`](../backend/agentflow/api/routes_chat.py) | `/api/chat` | Chat with the traffic-control model. |
| [`routes_queue.py`](../backend/agentflow/api/routes_queue.py) | `/api/queue` | What the controller has cued up per agent. |
| [`routes_state.py`](../backend/agentflow/api/routes_state.py) | `/api` | Durable state surface: timeline events (incl. `/api/events` + `/api/events/stream` SSE), run ledger, approvals. |
| [`routes_preview.py`](../backend/agentflow/api/routes_preview.py) | `/api/preview` | Run the workspace dev server and report reachability. |

**Belongs here:** request validation, status codes, response shaping, streaming
plumbing. **Does NOT belong here:** business logic or direct state mutation —
keep routers thin and call services. A new resource = a new `routes_<name>.py`
plus one `include_router(...)` line in `app.py`.

---

## `backend/tests/` — pytest suite

Hermetic backend tests (~165 tests). [`conftest.py`](../backend/tests/conftest.py)
has an autouse fixture redirecting `~/.agentflow` and `$HOME` to a per-test temp
dir, so tests **never** touch the developer's real global state. Files are
`test_<area>.py`, roughly one per service/concern (e.g.
[`test_task_service.py`](../backend/tests/test_task_service.py),
[`test_queue_service.py`](../backend/tests/test_queue_service.py),
[`test_recovery.py`](../backend/tests/test_recovery.py),
[`test_contracts.py`](../backend/tests/test_contracts.py),
[`test_headroom_service.py`](../backend/tests/test_headroom_service.py),
[`test_pillars.py`](../backend/tests/test_pillars.py), plus security/CSRF/redaction
and streaming tests). Run with `make test-backend` (`pytest backend/tests --cov=agentflow`).

**Belongs here:** backend unit/integration tests. New service ⇒ new
`test_<service>.py`; reuse the autouse isolation fixture rather than touching
real state.

---

## `frontend/` — React SPA

Vite 5 + React 18 + Tailwind + xterm. Dev server on `:5180` proxies `/api`
(see [`vite.config.ts`](../frontend/vite.config.ts)); production build (`tsc &&
vite build`) emits `frontend/dist/`, which the backend serves on `:8787`.

```
frontend/
├── index.html              # Vite HTML entry (mounts #root, links manifest)
├── vite.config.ts          # dev server :5180, /api proxy, build output
├── tailwind.config.js / postcss.config.js / tsconfig.json
├── eslint.config.js / .prettierrc.json / .prettierignore
├── package.json            # scripts: dev, build, test (vitest), lint, typecheck, format
├── public/                 # copied verbatim into dist (NOT processed by Vite)
│   ├── manifest.webmanifest, sw.js   # PWA / Chrome app-mode
│   └── icons/              # bean-{192,512}.png, maskable variants, *.svg
└── src/                    # application source (below)
```

> `frontend/public/` is static and copied as-is — put PWA/service-worker/icon
> assets here, not in `src/`. See [docs/pwa-chrome-app-mode.md](pwa-chrome-app-mode.md).

### `frontend/src/` — entry & core

| File | Role |
| --- | --- |
| [`main.tsx`](../frontend/src/main.tsx) | React entry; mounts `<App/>` into `#root`. |
| [`App.tsx`](../frontend/src/App.tsx) | Top-level shell: activity bar, page routing, panel layout. |
| [`api.ts`](../frontend/src/api.ts) | Typed client for every `/api/*` endpoint — the one place that talks HTTP. |
| [`types.ts`](../frontend/src/types.ts) | Shared TS types mirroring backend payloads. |
| [`stream.tsx`](../frontend/src/stream.tsx) | Live event-stream subscription (SSE + polling fallback) via `useSyncExternalStore`. |
| [`persist.ts`](../frontend/src/persist.ts) | `localStorage` helpers so UI state (tabs, panels, expanded folders) survives reloads. |
| [`styles.css`](../frontend/src/styles.css) | Tailwind layers + global styles. |

### `frontend/src/components/` — reusable UI

Presentational + small stateful widgets shared across pages. Highlights:
`ActivityBar` / `StatusBar` (shell chrome), `ChatPanel` + `Composer` (controller
chat), `Markdown` + `SmoothStreamingText` + `TimelineCard` + `RawDetail`
(Pillar 3 readable streaming presentation), `TaskViews`, `FileTree` /
`FileTypeIcon` / `CodeReader` (workspace browsing), `SourceControlPanel` (git),
`ProviderCard` / `UsageHealthBadge` / `BudgetModePicker` /
`RoutingRecommendationCard` (providers & budget), `CommandPalette`, `LogConsole`,
`DragHandle` (VS Code-style pane resizer), `ErrorBoundary`, `ArtifactChip`,
`StatusBadge`, and the `icons.tsx` / `ui.tsx` primitives. Component tests live
beside their component as `*.test.tsx` (e.g. `Markdown.test.tsx`,
`ErrorBoundary.test.tsx`).

**Belongs here:** UI used by more than one page, or generic widgets. Page-specific
view logic belongs under the page's folder (see `pages/tasks/`).

### `frontend/src/pages/` — top-level screens

One file per activity-bar destination: `ProjectsPage`, `AgentsPage`, `TasksPage`,
`TerminalsPage`, `UsagePage`, `LogsPage`, `PreviewPage`, `SettingsPage`. The
**`pages/tasks/`** subfolder holds the Tasks screen's decomposed pieces:
`StepChat.tsx`, `TaskFlowChart.tsx`, `TaskStatusPanels.tsx`, and the
presentation/model helper `taskPageModel.ts`. Pattern to follow: when a page
grows beyond one file, give it a `pages/<page>/` folder for its sub-views and a
local `*Model.ts`.

### `frontend/src/lib/` — pure helpers (with tests)

Framework-light utilities, each with a colocated `*.test.ts`:
[`ansi.ts`](../frontend/src/lib/ansi.ts) (Pillar 3 ANSI stripping),
[`streamEvent.ts`](../frontend/src/lib/streamEvent.ts) (event normalisation),
[`displayModel.ts`](../frontend/src/lib/displayModel.ts) (shared deterministic
display model for controller tab + Tasks page), and
[`taskFormat.ts`](../frontend/src/lib/taskFormat.ts) (Tasks-tab presentation,
budget/prompt parsing). **Belongs here:** deterministic, testable, React-free
logic. No JSX, no API calls.

### `frontend/src/hooks/` — React hooks

Reusable stateful behaviour. [`useAutoScroll.ts`](../frontend/src/hooks/useAutoScroll.ts)
(stick-to-bottom for live output), with `useAutoScroll.test.ts`. New cross-page
hooks go here; one-off hooks can stay with their component.

### `frontend/src/test/`

[`setup.ts`](../frontend/src/test/setup.ts) — vitest/jsdom test bootstrap. Actual
tests live next to the code they cover (`*.test.ts[x]`), not in this folder.

---

## `scripts/` — operational shell scripts

| Script | Purpose | Status |
| --- | --- | --- |
| [`install.sh`](../scripts/install.sh) | One-time setup: Python ≥3.11 venv + backend deps + `npm install`. Backs `make setup`. | Canonical |
| [`dev.sh`](../scripts/dev.sh) | Run backend `:8787` + Vite dev server `:5180`. Backs `make dev`. | Canonical |
| [`headroom.sh`](../scripts/headroom.sh) | Start the Headroom token-saving proxy (Pillar 1). Pairs with `headroom_service.py`. | Canonical |
| [`app.sh`](../scripts/app.sh) | Single-port launcher: build frontend if needed, start backend, open Chrome `--app` window. | Launcher |
| [`app-mode.sh`](../scripts/app-mode.sh) | Start backend if unhealthy, wait, open Chrome `--app` window. | Launcher (overlaps `app.sh`) |
| [`make-app.sh`](../scripts/make-app.sh) | Build `dist-app/CLIT Controller.app` thin bundle that runs `app.sh`. | Packaging |
| [`create-macos-app-mode.sh`](../scripts/create-macos-app-mode.sh) | Build `dist/CLIT Controller IDE.app` thin wrapper that runs `app-mode.sh`. | Packaging (overlaps `make-app.sh`) |

> **Redundant/overlapping launchers — consolidate before adding more.** There are
> two parallel "open as a Chrome app" paths: `app.sh` + `make-app.sh` (→
> `dist-app/`) and `app-mode.sh` + `create-macos-app-mode.sh` (→ `dist/`). They do
> nearly the same thing with different output dirs. Both are documented in
> [docs/pwa-chrome-app-mode.md](pwa-chrome-app-mode.md). Prefer one pair for new
> work rather than introducing a third launcher. `install.sh`, `dev.sh`, and
> `headroom.sh` are the non-overlapping, canonical scripts.

---

## `docs/` — documentation

Normative docs at the top level — link to these, don't duplicate:
[ARCHITECTURE.md](ARCHITECTURE.md), [OPERATIONS.md](OPERATIONS.md),
[SECURITY.md](SECURITY.md), [ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md),
[PILLARS.md](PILLARS.md), and this file. Narrative/feature design notes
(`live-output-everywhere.md`, `streaming-renderer-decision.md`,
`task-controller-io-surface.md`, `vscode-style-agent-dock.md`,
`pwa-chrome-app-mode.md`, `local-voice-io.md`, `phase-1-5-product-workbench.md`,
etc.) capture decisions and are explanatory, not contracts. Subfolders:

- **[`docs/audit/`](audit/)** — [`INITIAL_AUDIT.md`](audit/INITIAL_AUDIT.md)
  (findings, e.g. P1-09 CSRF) and [`FINAL_REPORT.md`](audit/FINAL_REPORT.md)
  (remediation). Append new audit rounds here.
- **[`docs/adr/`](adr/)** — Architecture Decision Records, numbered
  (`NNNN-title.md`), starting at
  [`0001-auto-run-policy-allowlist.md`](adr/0001-auto-run-policy-allowlist.md).
  A significant decision = a new sequential ADR; don't edit accepted ones, supersede them.
- **[`docs/orchestrator-backend/`](orchestrator-backend/)** — design series
  (target capability, contracts, roadmap, verification/ops) referenced from
  service docstrings (e.g. the Policy Contract).
- **`docs/assets/`**, **`docs/icon-options/`** — screenshots and icon design
  candidates used by docs/README; not shipped to the app (app icons live in
  `frontend/public/icons/`).

---

## Build output & generated areas (do not edit / do not commit)

- **`frontend/dist/`** — Vite production build; backend serves it for single-port
  mode. Regenerate with `make build`. Gitignored.
- **`/dist/`** — generated `CLIT Controller IDE.app` wrapper from
  `create-macos-app-mode.sh`. Gitignored (`/dist`).
- **`dist-app/`** — generated `CLIT Controller.app` bundle from `make-app.sh`.
  Gitignored.
- **`.venv/`** — backend virtualenv (Python 3.11). **`node_modules/`** — frontend
  deps. Caches: `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.coverage`,
  `frontend/coverage/`. All gitignored; remove with `make clean`.

---

## Where new code goes (quick reference)

- **New API endpoint** → `backend/agentflow/api/routes_<resource>.py` (thin) +
  one `include_router` in `app.py`; business logic in a service module; request
  shape in `models.py`; durable output shape (if structured) as a versioned
  contract in `contracts.py`.
- **New filesystem path** → add a helper to `paths.py` (never hardcode).
- **New backend behaviour** → a service module under `backend/agentflow/` + a
  `backend/tests/test_<service>.py`.
- **New UI screen** → `frontend/src/pages/<Page>.tsx` (+ `pages/<page>/` folder
  if it grows); shared widget → `components/`; pure helper → `lib/` (+ test);
  reusable hook → `hooks/`; static asset → `frontend/public/`.
- **Significant decision** → new ADR in `docs/adr/`. **Audit work** → `docs/audit/`.

Follow the conventions and verification gates in
[docs/ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md); the single command
surface is the [Makefile](../Makefile) (`make verify` mirrors CI in
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml)).
