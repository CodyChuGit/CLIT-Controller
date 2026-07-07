# Orchestrator Rebase + Codebase-Memory Graph + opensrc — Design

**Date:** 2026-07-07
**Status:** Approved (design) — pending implementation plan
**Scope choice:** All three subsystems in one combined spec, built foundation-first.

---

## 1. Summary

Three changes to AgentComposer (a.k.a. AgentFlow Studio), delivered together:

1. **Rebase the agent-use logic** onto the pure-stdlib orchestration core from the
   `Agent_CLI_Skill` project (`/Users/cody/Agent_CLI_Skill/agent-orchestrator`). The engine
   becomes the decision brain for *who runs a unit of work, on what model, with what fallback*,
   and its multi-agent **stage pipelines** replace the app's fixed 4-step task flow. The proven
   execution body (subprocess spawning, PTY terminals, CLITC controller) is kept.
2. **Integrate `codebase-memory-mcp`** (a C binary that indexes a repo into a SQLite knowledge
   graph) and add a **native 3D "Graph Visualization" tab**, styled with AgentComposer's own
   design system (ui-ux-pro-max) rather than iframing the binary's stock UI.
3. **Integrate `opensrc`** (Vercel Labs; `opensrc path <pkg>` fetches + caches any package's real
   source) as a **first-class agent tool + a "Sources" browse tab**, so every agent can read the
   actual source of any open-source dependency on demand.

Delivery order: (1) is the foundation; (2) and (3) are independent of each other and layer on top.

---

## 2. Context (current state)

**Agents today are subprocess CLIs.** AgentComposer spawns local CLIs (`claude`, `codex`,
`antigravity`/`agy`) with a constructed prompt and streams their output back over SSE/WS. Relevant
files (from codebase survey):

- **Decision logic (to be rebased):**
  - `backend/agentflow/routing_service.py` — ad-hoc budget-aware `recommend(usage, task_type)`.
  - `backend/agentflow/config.py` — static per-workspace routing `{orchestrator, pm, engineer, qa}`
    (`get_workspace_routing`), and `DEFAULT_COMMAND_TEMPLATES` (per-provider argv templates).
  - `backend/agentflow/task_service.py` — the **fixed** step flow `codex_spec → claude_implement →
    qa → codex_review` (`run_step`, `run_full`, `step_provider`).
  - `backend/agentflow/prompt_templates.py` — one prompt factory per step/role.
- **Execution body (to be kept):**
  - `backend/agentflow/process_runner.py` — `RUNNER.start()` spawns the CLI, streams, redacts,
    enforces `AGENT_RUN_TIMEOUT`, heartbeats.
  - `backend/agentflow/terminal_service.py` — PTY sessions.
  - `backend/agentflow/controller_protocol.py` + `controller/engine.py` + `controller/actions.py` —
    the `CLITC_RESULT_V1` action protocol (`queue_steps`, `run_command`, `complete_task`, …).
  - `backend/agentflow/queue_service.py` — durable queue + `dispatcher_loop()`.
  - `backend/agentflow/usage_service.py` — per-provider health (green/yellow/red), cost.
  - `backend/agentflow/provider_probe.py` — CLI detection/version/install/login.
  - `backend/agentflow/policy_service.py` — command allow/deny/require-approval.
- **Frontend:** React + Vite + **Tailwind** (`frontend/src/styles.css`). Page routing in
  `App.tsx`; left rail `components/ActivityBar.tsx`; pages under `frontend/src/pages/`; HTTP client
  `api.ts`; SSE store `stream.tsx`; types `types.ts`. New top-level screens are added as a page +
  an ActivityBar entry.

**The engine core (to be imported).** `/Users/cody/Agent_CLI_Skill/agent-orchestrator/scripts` —
pure-stdlib Python, no PyYAML/jsonschema. Import-friendly public functions:

- `route_task.route(task_type=None, text=None, long_running=False, large_logs=False, task_id=None,
  policy=None)` → dict `{decision, primary_agent, stages:[{agent, persona, action,
  parallel_group}], monitor, confidence, rationale, …}`. `ROUTE_TABLE` covers ~67–80 task types →
  15 decision classes (incl. pipelines like `FRONTEND_QA_FIX_LOOP`,
  `RESEARCH_THEN_IMPLEMENT_THEN_VALIDATE`).
- `dispatch.dispatch_plan(decision, caps, policy=None, usage_state=None)` → `{dispatch:[…],
  usage_fallbacks:[…]}`. `DEFAULT_POLICY` supports **`mode: "cli_only"`** (no Claude-Code plugins),
  which maps directly onto AgentComposer spawning CLIs.
- `usage_lib.resolve(agent, caps, state, policy, now_ts)` → `(effective_agent, hops)` via
  spread-first fallback chains; `mark(...)`, `detect_exhaustion(agent, text)`, `load_state()`,
  `save_state()`, `report()`. State file: `.claude-runtime/agent-usage.json`.
- `monitor_lib.classify_deterministic(...)`, `build_completion_event(...)` — long-running job
  supervision (used for `*_WITH_OMLX_MONITOR`).
- Config: `config/routing-policy.yaml`, `dispatch-policy.yaml`, `fallback-policy.yaml`,
  `personas.yaml`, etc.

Engine agents `{claude, codex, antigravity, omlx}` — the first three already equal AgentComposer's
provider ids; **oMLX has no chat provider** (monitor role only).

**Two new external tools:**

- `codebase-memory-mcp` — single static C binary. Modes: MCP (stdio), **CLI**
  (`codebase-memory-mcp cli <tool_name> '<json_args>'`), UI (`--ui=true --port=9749`). We use **CLI
  mode** and render our own tab, so we need only the **standard binary**, not the UI variant. 14
  tools incl. `index_repository`, `index_status`, `list_projects`, `search_graph`,
  `get_graph_schema`, `get_architecture`, `get_code_snippet`, `trace_path`, `query_graph`,
  `detect_changes`. Store: SQLite at `~/.cache/codebase-memory-mcp/`. Data model: node labels
  `Project/Package/Folder/File/Module/Class/Function/Method/Interface/Enum/Type/Route/Resource`;
  edge types `CALLS/IMPORTS/IMPLEMENTS/DEFINES/HTTP_CALLS/DATA_FLOWS/…`.
- `opensrc` — Rust CLI, `npm install -g opensrc`. `opensrc path <pkg>` fetches+caches a package's
  real source and prints a local filesystem path. Registries: bare npm name, `pypi:<pkg>`,
  `crates:<pkg>`, `github:<owner>/<repo>`.

---

## 3. Goals / Non-goals

**Goals**
- Every provider/model/fallback decision in the app flows through the engine core.
- Task execution is driven by engine **stages**, not a hardcoded 4-step sequence.
- A native, app-themed 3D knowledge-graph tab backed by `codebase-memory-mcp`.
- A first-class opensrc capability: a controller tool + a browse tab + raw-CLI-agent access.
- `make verify` (ruff + mypy + pytest + vitest) stays green; new code is tested at its boundaries.

**Non-goals**
- Rewriting `process_runner`, PTY terminals, SSE, or the CLITC protocol wire format.
- Re-testing the engine core (it ships its own `--self-check` suite); we test only the adapter
  boundary.
- Using `codebase-memory-mcp`'s stock 3D UI or MCP-stdio transport (we use CLI mode).
- Adopting Claude-Code plugin dispatch (`codex:codex-rescue`, `agy:runner`) inside the app — the app
  *is* its own dispatch mechanism; we run the engine in `cli_only` mode.

---

## 4. Architecture overview

```
┌───────────────────────── AgentComposer (existing body — KEPT) ──────────────────────────┐
│ React/Vite/Tailwind UI ─ FastAPI ─ chat_service · task_service · queue_service           │
│ process_runner (spawns CLIs) · PTY terminals · CLITC controller · usage · policy         │
└──────▲────────────────────────────▲────────────────────────────▲────────────────────────┘
       │ WHO/model/fallback          │ graph data                  │ source fetch + tool
┌──────┴─────────────────────┐ ┌─────┴──────────────────┐ ┌────────┴───────────────────┐
│ orchestrator/  (NEW adapter)│ │ memory_service  (NEW)  │ │ opensrc_service  (NEW)     │
│  router · dispatch_adapter  │ │  → codebase-memory-mcp │ │  → opensrc CLI             │
│  usage_bridge · caps · _engine│ │   `cli` mode (JSON)  │ │  fetch/tree/read/search    │
└──────┬─────────────────────┘ └─────┬──────────────────┘ └────────┬───────────────────┘
       │ imports (pure-stdlib)        │ nodes+edges              │ local paths
┌──────┴─────────────────────┐ ┌─────┴──────────────────┐ ┌────────┴───────────────────┐
│ Agent_CLI_Skill CORE        │ │ Memory tab (NEW)       │ │ Sources tab (NEW)          │
│ route()→dispatch(cli_only)  │ │  3D force graph        │ │  search · tree · viewer    │
│ →usage_lib.resolve()        │ │  react-force-graph-3d  │ │  reuse FileTree + editor   │
│ monitor_lib                 │ │  ui-ux-pro-max themed  │ │  ui-ux-pro-max themed      │
└─────────────────────────────┘ └────────────────────────┘ └────────────────────────────┘
      routes to → codex · claude · antigravity(agy) · oMLX(monitor)
```

---

## 5. Subsystem A — Orchestrator engine rebase (foundation)

### 5.1 New adapter package: `backend/agentflow/orchestrator/`

| Module | Responsibility |
|--------|----------------|
| `_engine.py` | Locate the engine and import it once. Resolution order: `AGENTCLI_CORE_PATH` env → default `/Users/cody/Agent_CLI_Skill/agent-orchestrator/scripts` → **vendored snapshot** `backend/agentflow/orchestrator/_engine_snapshot/`. Inserts the resolved dir on `sys.path` and re-exports `route_task`, `dispatch`, `usage_lib`, `monitor_lib`. Single point of coupling to the engine. |
| `router.py` | `route_for_task(task)` / `route_for_text(text, **signals)` → calls `route_task.route(...)`; returns a normalized `RouteResult` (decision, stages, monitor, confidence, rationale). Maps AgentComposer task metadata → engine `task_type`/`text`/`long_running`/`large_logs`. |
| `dispatch_adapter.py` | `plan(decision, caps, usage_state)` → `dispatch.dispatch_plan(decision, caps, policy={"mode":"cli_only", ...}, usage_state)`. Translates each resolved stage → `{provider_id, command_template, model}` consumable by `process_runner`. Engine agent → provider map: `codex→codex`, `claude→claude`, `antigravity→antigravity`, `omlx→<monitor, no provider>`. |
| `usage_bridge.py` | Two-way sync between engine `usage_lib` state and `usage_service` health. `on_provider_health(provider, health)` → `usage_lib.mark(exhausted)` when RED; `on_run_output(provider, text)` → `usage_lib.detect_exhaustion` → mark + record fallback; `snapshot()` → surface fallback events to the Usage UI. |
| `caps.py` | Build the engine `caps` dict (`{codex_cli, agy_cli, omlx, codex_plugin:false, agy_plugin:false}`) from `provider_probe.py`. Plugins always false (cli_only). |
| `personas.py` | Persona registry + `persona_prompt(persona, ctx)`: **one parameterized builder** seeded from the engine `personas.yaml`, with a generic fallback. Not 24 hand-written templates. |

### 5.2 Integration points (existing files changed)

1. **`routing_service.py`** — `recommend()` delegates to `orchestrator.router` + `usage_bridge`.
   Keep the budget-context header behavior (it still prepends cost/health to prompts); the engine
   now owns the who/model/fallback outcome. The function's return shape is preserved so callers and
   the Usage UI don't change.
2. **`config.py`** — `get_workspace_routing()` keeps user overrides (they *win*), but the default
   role→provider mapping is derived from engine decisions instead of the static table.
   `DEFAULT_COMMAND_TEMPLATES` unchanged (still the argv source).
3. **`task_service.py`** — replace the fixed step sequence with engine **stages**:
   - On task run, classify the task (`route_for_text(task.goal)` or an explicit `task.task_type`),
     obtain `stages`.
   - Enqueue stages through `queue_service`. Each stage → a run via `process_runner` using the
     provider/model from `dispatch_adapter` and the prompt from `personas.persona_prompt`.
   - `parallel_group`: when two adjacent stages share a group id, the dispatcher runs them
     concurrently; otherwise sequential (minimal extension to `dispatcher_loop`).
   - Keep the task-folder artifact convention and `orchestrator_consult` transitions; the consult
     step now asks the engine (via `router`) for the next stage instead of a hardcoded next step.
4. **`prompt_templates.py`** — the step-specific factories are refactored to call
   `orchestrator.personas.persona_prompt`. Legacy step names (`codex_spec`, …) map to their
   equivalent personas for backward compatibility of existing tasks.
5. **`usage_service.py`** — emits health changes into `usage_bridge`; consumes fallback snapshots
   for display.
6. **`provider_probe.py`** — add `omlx` capability probing (already lists it) surfaced into `caps`.
7. **Monitoring** — for decisions carrying a monitor (`*_WITH_OMLX_MONITOR`), the run is wrapped
   with `monitor_lib` classification; if `omlx` is absent the engine's own fallback chain applies
   (Codex triage → agy summary → deterministic). Graceful when nothing is installed.

### 5.3 Packaging decision (resolves open decision #1)

Use `_engine.py` as the single coupling point (env → user path → vendored snapshot). Add
`scripts/sync-engine.sh` to refresh the committed snapshot under
`backend/agentflow/orchestrator/_engine_snapshot/` so `make verify`/CI works on machines without the
skill checked out. This keeps one source of truth in day-to-day dev (imports the live skill) while
staying self-contained for CI. (Editable `pip install -e` remains a future option if the skill is
later published as a package; not required now.)

---

## 6. Subsystem B — codebase-memory-mcp + 3D graph tab

### 6.1 Backend `backend/agentflow/memory_service.py`

- Detect/install the **standard** binary via `provider_probe` (add `codebase-memory-mcp` to the
  detection + Agents install flow; install gated by approval/policy).
- All queries go through CLI mode: `codebase-memory-mcp cli <tool> '<json>'` (subprocess, reusing
  the app's existing subprocess conventions; JSON in/out).
- Wrapped tools: `index_repository`, `index_status`, `list_projects`, `delete_project`,
  `search_graph`, `get_graph_schema`, `get_architecture`, `get_code_snippet`, `trace_path`,
  `query_graph`, `detect_changes`.
- Auto-index the active workspace on open (async, non-blocking); expose progress via `index_status`.
- Normalize graph payloads to render-ready shape:
  `{nodes:[{id, label, name, file, degree}], edges:[{source, target, type}]}`.

### 6.2 API `backend/agentflow/api/routes_memory.py`

| Method + path | Backing tool |
|---------------|--------------|
| `POST /api/memory/index` | `index_repository` (active workspace) |
| `GET  /api/memory/status` | `index_status` |
| `GET  /api/memory/graph?label=&name=&limit=&depth=` | `search_graph` (+ `trace_path` for depth) |
| `GET  /api/memory/schema` | `get_graph_schema` (legend/filter counts) |
| `GET  /api/memory/architecture` | `get_architecture` (hotspots/clusters/routes) |
| `GET  /api/memory/snippet?qname=` | `get_code_snippet` |
| `GET  /api/memory/trace?qname=&depth=` | `trace_path` |
| `POST /api/memory/query` | `query_graph` (advanced Cypher-like) |

Add matching client functions to `frontend/src/api.ts` and types to `types.ts`.

### 6.3 Frontend `frontend/src/pages/MemoryPage.tsx` + ActivityBar "Memory"

- **`react-force-graph-3d`** (one new frontend dep; brings Three.js). Themed with app tokens via
  **ui-ux-pro-max**: node color keyed by label, link color keyed by edge type, dark surface = app
  background, subtle glow acceptable, no gradients on chrome.
- Controls panel (themed): label filter, name search (→ `/graph?name=`), depth slider (→ trace),
  edge-type toggles, "Index now" button + live status, architecture side-panel (hotspots/clusters).
- Node click → drawer showing `get_code_snippet` + callers/callees (`trace_path`), reusing the
  existing `.mono-block`/code-view styling.
- Register the page in `App.tsx` routing and add an `ActivityBar.tsx` entry (icon: network/graph).

---

## 7. Subsystem C — opensrc first-class tool + Sources tab

### 7.1 Backend `backend/agentflow/opensrc_service.py`

- Ensure `opensrc` installed (add to `provider_probe`; `npm i -g opensrc` behind approval).
- Functions (subprocess): `fetch(pkg) → path` (`opensrc path <pkg>`), `list_cached()`,
  `tree(pkg)`, `read(pkg, relpath)`, `search(pkg, query)` (ripgrep within the cached path).
- Registry-prefixed specs supported: bare npm, `pypi:`, `crates:`, `github:owner/repo`.

### 7.2 API `backend/agentflow/api/routes_opensrc.py`

| Method + path | Action |
|---------------|--------|
| `POST /api/opensrc/fetch` | fetch+cache, returns `{pkg, path, files}` |
| `GET  /api/opensrc/list` | cached packages |
| `GET  /api/opensrc/tree?pkg=` | file tree |
| `GET  /api/opensrc/file?pkg=&path=` | file contents |
| `GET  /api/opensrc/search?pkg=&q=` | ripgrep matches |

### 7.3 Agent access (two paths — satisfies "all agents can crawl OSS repos")

- **Controller tool:** add an `opensrc` action to `controller_protocol.py`'s `ControllerAction`
  union and `controller/actions.py` `execute()` — the orchestrator can fetch a package and cite
  snippets back into the transcript.
- **Raw CLI agents:** put `opensrc` on PATH, add a `policy_service` allow-rule for `opensrc path`,
  and add a capability line to the persona prompts so `codex`/`claude`/`agy` know they may call
  `opensrc path <pkg>` and read the source directly in their own shell.

### 7.4 Frontend `frontend/src/pages/SourcesPage.tsx` + ActivityBar "Sources"

- Registry-prefixed search bar, Fetch button, cached-packages list.
- Browse pane: **reuse `components/FileTree.tsx` + the existing code viewer** (do not rebuild the
  tree). ui-ux-pro-max themed. Register page in `App.tsx` + `ActivityBar.tsx` (icon: package/box).

---

## 8. Cross-cutting

- **Dependencies:** frontend `react-force-graph-3d`. Backend: no new PyPI runtime dep (engine
  imported via `_engine.py`). External binaries: `codebase-memory-mcp`, `opensrc` — detected +
  installed through the existing Agents flow.
- **Config:** surface engine tunables (routing/dispatch/fallback highlights) in `SettingsPage.tsx`;
  ship sane defaults. Engine config files live with the engine (or its snapshot).
- **Safety / policy:** opensrc *fetch* is a read-only download (allowed); binary/global installs
  stay behind the existing approval gate. Redaction continues to run through `process_runner`.
  `query_graph`/`search` inputs are validated (read-only Cypher only).
- **Testing (`make verify` stays green):**
  - Python unit tests at the adapter boundary: `router` mapping, `dispatch_adapter` cli_only
    translation, `usage_bridge` exhaustion→mark→fallback, `personas.persona_prompt`.
  - `memory_service` / `opensrc_service` tested against a **fake binary** (script on PATH emitting
    canned JSON), so tests are offline and deterministic.
  - vitest smoke tests for `MemoryPage` and `SourcesPage` (render + basic interaction, mocked API).
  - Engine core is **not** re-tested here.

---

## 9. Decisions (confirmed)

1. **Rebase depth:** brain swap **+ engine stage pipelines** (task_service adopts engine `stages`).
2. **Graph tab:** native **3D force graph** (`react-force-graph-3d`), app-themed.
3. **opensrc:** **first-class tool + browse tab** (controller action + Sources page + raw-CLI access).
4. **Engine consumption:** imported in-process via `_engine.py` (env → user path → vendored
   snapshot), `cli_only` dispatch mode. Not subprocess, not plugin dispatch.
5. **Memory transport:** binary **CLI mode**, standard binary (no UI variant, no MCP stdio).
6. **New screens:** two top-level ActivityBar tabs — "Memory" and "Sources".
7. **User model overrides win** over engine model tiers.

---

## 10. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Engine path coupling breaks CI | `_engine.py` resolution + committed snapshot via `sync-engine.sh`. |
| Stage-pipeline rewrite regresses existing tasks | Legacy step names map to personas; keep task-folder artifacts + consult flow; migrate behind tests. |
| `react-force-graph-3d` bundle weight (Three.js) | Desktop dev tool; lazy-load the Memory route so it doesn't tax initial load. |
| Provider/agent id drift between engine and app | Single map in `dispatch_adapter`; unit-tested. oMLX explicitly monitor-only. |
| Large repos slow `index_repository` | Async index + `index_status` progress; never block the UI. |
| opensrc/codebase-memory not installed | `provider_probe` detects; features degrade gracefully with an install CTA. |

---

## 11. Testing strategy (summary)

Boundary-first, offline, deterministic. Adapter unit tests + fake-binary service tests + page smoke
tests. `make verify` (ruff, mypy, pytest, vitest) is the gate. No network in tests.

---

## 12. Implementation sequencing

1. **Foundation (A):** `_engine.py` + snapshot + `caps` → `router` → `dispatch_adapter` →
   `usage_bridge` → wire `routing_service`/`config` → migrate `task_service` to stages →
   `personas`. Land with adapter tests green.
2. **B and C in parallel** (independent): memory_service + routes + MemoryPage; opensrc_service +
   routes + controller action + SourcesPage.
3. Settings surface, docs (README/DESIGN), final `make verify`.

Each subsystem is independently testable and independently revertable.
