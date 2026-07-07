# Orchestrator Rebase + Codebase-Memory Graph + opensrc — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: this repo executes via the `agent-orchestrator` skill (route to Codex/agy, Claude reviews). Steps use checkbox (`- [ ]`) syntax for tracking. Every task ends TDD-style: failing test → minimal impl → green → commit. Executors are capable coding agents, so code sketches show intent/signatures; fill implementation against the live code.

**Goal:** Rebase AgentComposer's agent decisions onto the `Agent_CLI_Skill` orchestration core (engine stages + spread-first fallback), and add a codebase-memory 3D graph tab and an opensrc source tool + browse tab.

**Architecture:** A new `backend/agentflow/orchestrator/` adapter imports the pure-stdlib engine (`route_task`/`dispatch`/`usage_lib`/`monitor_lib`) in `cli_only` mode and feeds decisions to the existing `process_runner`/queue/CLITC body. Two new backend services shell out to the `codebase-memory-mcp` and `opensrc` binaries; two new React pages render their data, themed with ui-ux-pro-max.

**Tech Stack:** Python 3.11 / FastAPI (backend), React + Vite + Tailwind (frontend), pure-stdlib engine, `react-force-graph-3d` (new FE dep), external binaries `codebase-memory-mcp` + `opensrc`.

## Global Constraints

- Engine is **pure-stdlib** (no PyYAML/jsonschema); consume via `_engine.py`, never copy logic.
- Engine runs in **`cli_only`** dispatch mode. Engine agents map: `codex→codex`, `claude→claude`, `antigravity→antigravity`, `omlx→monitor-only (no provider)`.
- **User model overrides win** over engine model tiers.
- Memory uses the **standard binary, CLI mode** (`codebase-memory-mcp cli <tool> '<json>'`) — no UI variant, no MCP stdio.
- Binary/global installs stay behind the existing **approval/policy** gate; opensrc *fetch* is allowed (read-only).
- `make verify` (ruff + mypy + pytest + vitest) is the gate. **Tests are offline** — services test against a fake binary on PATH. Do **not** re-test the engine core.
- Follow existing patterns: subprocess via `process_runner` conventions; new screens = page + `ActivityBar` entry; Tailwind utility classes + existing `.btn/.card/.mono-block`.

---

# Phase A — Foundation: orchestrator engine rebase

### Task A1: Engine loader + snapshot + capabilities

**Files:**
- Create: `backend/agentflow/orchestrator/__init__.py`, `backend/agentflow/orchestrator/_engine.py`, `backend/agentflow/orchestrator/caps.py`
- Create: `scripts/sync-engine.sh` (rsync engine `scripts/`+`config/` → `backend/agentflow/orchestrator/_engine_snapshot/`)
- Test: `backend/tests/orchestrator/test_engine_load.py`

**Interfaces:**
- Produces: `orchestrator._engine.load() -> module namespace` exposing `route_task, dispatch, usage_lib, monitor_lib`; `orchestrator.caps.build_caps() -> dict` (`{codex_cli,agy_cli,omlx,codex_plugin:False,agy_plugin:False}`).

- [ ] **Step 1 — failing test:** `test_engine_exposes_route_and_dispatch()` imports `orchestrator._engine`, calls `load()`, asserts `hasattr(ns.route_task, "route")` and `hasattr(ns.dispatch, "dispatch_plan")`.
- [ ] **Step 2 — run, expect fail** (`pytest backend/tests/orchestrator/test_engine_load.py -v`).
- [ ] **Step 3 — implement `_engine.py`:** resolve dir in order `os.environ["AGENTCLI_CORE_PATH"]` → `/Users/cody/Agent_CLI_Skill/agent-orchestrator/scripts` → `<pkg>/_engine_snapshot/scripts`; `sys.path.insert(0, dir)` once (guard with a module global); `import route_task, dispatch, usage_lib, monitor_lib`; return a `SimpleNamespace`. Raise a clear `RuntimeError` if none resolve.
- [ ] **Step 4 — implement `caps.build_caps()`** from `provider_probe` (codex/agy/omlx presence).
- [ ] **Step 5 — write `scripts/sync-engine.sh`** and run it once to populate the snapshot (fallback for CI).
- [ ] **Step 6 — green + commit** (`feat(orchestrator): engine loader + capabilities`).

### Task A2: Router

**Files:** Create `backend/agentflow/orchestrator/router.py`; Test `backend/tests/orchestrator/test_router.py`

**Interfaces:**
- Consumes: `_engine.load()`.
- Produces: `router.route_for_text(text, *, long_running=False, large_logs=False, task_id=None) -> RouteResult`; `router.route_for_task(task) -> RouteResult`. `RouteResult` = dataclass `{decision:str, primary_agent:str, stages:list[Stage], monitor:str|None, confidence:float, rationale:str}`; `Stage` = `{agent:str, persona:str, action:str, parallel_group:str|None}`.

- [ ] **Step 1 — failing test:** `route_for_text("implement the core module")` returns a `RouteResult` with non-empty `stages`, each stage having `agent in {claude,codex,antigravity}` (map omlx out of agent stages), and `confidence > 0`.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement:** call `ns.route_task.route(text=..., long_running=..., large_logs=..., task_id=...)`; adapt the returned dict into `RouteResult`/`Stage` dataclasses. `route_for_task` derives `text` from `task.goal` (and honors an explicit `task.task_type` if present).
- [ ] **Step 4 — green + commit** (`feat(orchestrator): router over route_task.route`).

### Task A3: Dispatch adapter (cli_only → provider/model)

**Files:** Create `backend/agentflow/orchestrator/dispatch_adapter.py`; Test `backend/tests/orchestrator/test_dispatch_adapter.py`

**Interfaces:**
- Consumes: `RouteResult` (A2), `caps.build_caps()` (A1), engine `dispatch.dispatch_plan`.
- Produces: `dispatch_adapter.plan(route_result, usage_state=None) -> list[StagePlan]`; `StagePlan` = `{provider_id:str|None, model:str|None, persona:str, action:str, parallel_group:str|None, fallbacks:list[dict]}`.

- [ ] **Step 1 — failing test:** for a route decision `DELEGATE_TO_CODEX`, `plan(...)` yields a `StagePlan` with `provider_id=="codex"` and `model` set to the engine's codex tier; assert omlx stages produce `provider_id is None` (monitor).
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement:** call `ns.dispatch.dispatch_plan(decision_dict, caps, policy={"mode":"cli_only"}, usage_state)`; translate each resolved stage → `StagePlan` using the agent→provider map; carry `usage_fallbacks` into `fallbacks`.
- [ ] **Step 4 — green + commit** (`feat(orchestrator): cli_only dispatch adapter`).

### Task A4: Usage bridge (health ↔ exhaustion ↔ fallback)

**Files:** Create `backend/agentflow/orchestrator/usage_bridge.py`; Test `backend/tests/orchestrator/test_usage_bridge.py`

**Interfaces:**
- Consumes: engine `usage_lib`, `usage_service`.
- Produces: `usage_bridge.on_provider_health(provider, health)`; `usage_bridge.on_run_output(provider, text) -> effective_next|None`; `usage_bridge.snapshot() -> dict`.

- [ ] **Step 1 — failing test:** `on_provider_health("codex","red")` then `usage_lib.load_state()` shows codex `exhausted`; `on_run_output("codex", "<rate limit text>")` marks exhausted and returns the fallback agent per the chain.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement:** RED→`usage_lib.mark(exhausted)`; GREEN→`mark(available)`; `on_run_output` runs `usage_lib.detect_exhaustion` then `resolve`. Persist via `save_state`. `snapshot()` returns recent `events.fallbacks`/`exhaustions` for the Usage UI.
- [ ] **Step 4 — green + commit** (`feat(orchestrator): usage bridge`).

### Task A5: Persona prompt builder

**Files:** Create `backend/agentflow/orchestrator/personas.py`; Test `backend/tests/orchestrator/test_personas.py`

**Interfaces:**
- Produces: `personas.persona_prompt(persona:str, ctx:dict) -> str`. `ctx` carries `{usage_header, task_rel_dir, workspace_summary, transcript, message}` (subset per persona).

- [ ] **Step 1 — failing test:** `persona_prompt("implementer", ctx)` contains the task dir and an implementation directive; an unknown persona falls back to a generic template (still includes the budget/usage header).
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement:** ONE parameterized builder + a small registry seeded from engine `personas.yaml` (read via `_engine` `_lib.read_yaml`); map legacy step names (`codex_spec→spec-writer`, `claude_implement→implementer`, `qa→qa-runner`, `codex_review→reviewer`). Generic fallback for the rest.
- [ ] **Step 4 — green + commit** (`feat(orchestrator): persona prompt builder`).

### Task A6: Wire routing_service + config to the engine

**Files:** Modify `backend/agentflow/routing_service.py` (`recommend`), `backend/agentflow/config.py` (`get_workspace_routing`); Test `backend/tests/orchestrator/test_routing_integration.py`

**Interfaces:**
- Consumes: A2/A3/A4. Produces: unchanged public shapes of `recommend()` / `get_workspace_routing()` (callers + Usage UI untouched).

- [ ] **Step 1 — failing test:** `recommend(usage, task_type="FRONTEND_BUG_FIX")` returns a recommendation whose provider matches the engine decision; when codex is marked exhausted, the recommendation falls back per chain.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement:** `recommend` builds a `RouteResult` + `plan` and maps to the existing return shape (keep budget-header behavior). `get_workspace_routing` overlays user overrides on engine-derived defaults.
- [ ] **Step 4 — green + commit** (`refactor(routing): decisions via orchestrator engine`).

### Task A7: Task execution via engine stages

**Files:** Modify `backend/agentflow/task_service.py` (`run_step`/`run_full`/`step_provider`), `backend/agentflow/queue_service.py` (`dispatcher_loop` for `parallel_group`); Test `backend/tests/orchestrator/test_task_stages.py`

**Interfaces:**
- Consumes: `router.route_for_task`, `dispatch_adapter.plan`, `personas.persona_prompt`, existing `process_runner.RUNNER.start`.
- Produces: task run driven by `stages` instead of the fixed 4-step list.

- [ ] **Step 1 — failing test (fake runner):** running a task classified to a multi-stage decision enqueues one queue item per stage in order, each with the mapped provider; same-`parallel_group` stages are dispatched concurrently.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement:** on run, `route_for_task(task)` → `plan()` → enqueue stages; each dequeued stage builds its prompt via `persona_prompt` and starts a run; `orchestrator_consult` asks the router for the next stage. Legacy explicit-step API stays working (maps step→persona). Extend `dispatcher_loop` to run same-group items together.
- [ ] **Step 4 — green + commit** (`feat(tasks): drive execution from engine stages`).

### Task A8: prompt_templates → personas (backward-compat)

**Files:** Modify `backend/agentflow/prompt_templates.py`; Test `backend/tests/orchestrator/test_prompt_templates_compat.py`

- [ ] **Step 1 — failing test:** legacy `codex_spec_prompt(usage, dir)` still returns a spec-writer prompt (now routed through `personas.persona_prompt`).
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement:** re-point the step factories at `personas.persona_prompt` with the mapped persona; delete duplicated prose (DRY).
- [ ] **Step 4 — green + commit** (`refactor(prompts): route step templates through personas`).

---

# Phase B — codebase-memory-mcp + 3D graph tab

### Task B1: memory_service (CLI-mode wrapper)

**Files:** Create `backend/agentflow/memory_service.py`; Test `backend/tests/test_memory_service.py` (+ fixture fake binary `backend/tests/fakes/codebase-memory-mcp`)

**Interfaces:**
- Produces: `memory_service.index(workspace)`, `.status()`, `.graph(label=None,name=None,limit=200,depth=1) -> {nodes,edges}`, `.schema()`, `.architecture()`, `.snippet(qname)`, `.trace(qname,depth)`, `.query(cypher)`. Each shells `codebase-memory-mcp cli <tool> '<json>'` and parses JSON.

- [ ] **Step 1 — failing test:** with the fake binary on PATH emitting canned `search_graph` JSON, `graph()` returns normalized `{nodes:[{id,label,name,file,degree}], edges:[{source,target,type}]}`.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement** the subprocess wrapper + normalization; timeouts + redaction via existing helpers.
- [ ] **Step 4 — green + commit** (`feat(memory): codebase-memory-mcp cli wrapper`).

### Task B2: memory routes + FE client

**Files:** Create `backend/agentflow/api/routes_memory.py`; Modify `backend/agentflow/app.py` (register router), `frontend/src/api.ts`, `frontend/src/types.ts`; Test `backend/tests/test_routes_memory.py`

**Interfaces:** Endpoints per spec §6.2. FE: `api.memoryGraph(params)`, `memoryStatus()`, `memoryIndex()`, `memorySchema()`, `memoryArchitecture()`, `memorySnippet(qname)`, `memoryTrace(qname,depth)`.

- [ ] **Step 1 — failing test:** `GET /api/memory/schema` (fake binary) returns node/edge counts JSON; `POST /api/memory/index` starts indexing and `GET /api/memory/status` reports progress.
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement** routes (thin over `memory_service`) + FE client fns + types.
- [ ] **Step 4 — green + commit** (`feat(memory): HTTP routes + api client`).

### Task B3: binary detection + install

**Files:** Modify `backend/agentflow/provider_probe.py` (+ install command), `backend/agentflow/api/routes_agents.py` if needed; Test `backend/tests/test_provider_probe_memory.py`

- [ ] Detect `codebase-memory-mcp` (version/presence); expose install (curl one-liner) **behind approval**. Test presence/absence branches. Commit (`feat(memory): detect + install codebase-memory-mcp`).

### Task B4: MemoryPage 3D graph + ActivityBar

**Files:** Create `frontend/src/pages/MemoryPage.tsx`; Modify `frontend/src/App.tsx` (route, lazy-load), `frontend/src/components/ActivityBar.tsx` (entry + icon), `frontend/package.json` (`react-force-graph-3d`); Test `frontend/src/test/MemoryPage.test.tsx`

- [ ] **Step 1 — failing vitest:** MemoryPage renders a graph container and a "Index now" control; mocked `memoryGraph` populates node/link counts. (ui-ux-pro-max applied via skill during build.)
- [ ] **Step 2 — run, expect fail.**
- [ ] **Step 3 — implement:** `react-force-graph-3d` themed with app tokens (node color by label, link color by edge type); controls (label filter, name search, depth slider, edge-type toggles); lazy-load the route so Three.js isn't in the initial bundle.
- [ ] **Step 4 — green + commit** (`feat(memory): 3D graph tab`).

### Task B5: node drawer + architecture panel

**Files:** Modify `frontend/src/pages/MemoryPage.tsx`; Test extend `MemoryPage.test.tsx`

- [ ] Node click → drawer with `memorySnippet` + `memoryTrace` (callers/callees), reuse `.mono-block`; side panel from `memoryArchitecture` (hotspots/clusters). Test drawer opens + fetches on node select. Commit (`feat(memory): node drawer + architecture panel`).

---

# Phase C — opensrc tool + Sources tab

### Task C1: opensrc_service

**Files:** Create `backend/agentflow/opensrc_service.py`; Test `backend/tests/test_opensrc_service.py` (+ fake `opensrc` binary fixture)

**Interfaces:** `fetch(pkg)->{pkg,path}`, `list_cached()`, `tree(pkg)`, `read(pkg,relpath)`, `search(pkg,q)`. Registries: bare, `pypi:`, `crates:`, `github:owner/repo`.

- [ ] **Step 1 — failing test:** fake `opensrc path zod` prints a temp dir; `fetch("zod")` returns that path; `tree`/`read`/`search` operate on it.
- [ ] **Step 2 — run, expect fail.** **Step 3 — implement.** **Step 4 — green + commit** (`feat(opensrc): source fetch/browse service`).

### Task C2: opensrc routes + FE client

**Files:** Create `backend/agentflow/api/routes_opensrc.py`; Modify `app.py`, `frontend/src/api.ts`, `types.ts`; Test `backend/tests/test_routes_opensrc.py`

- [ ] Endpoints per spec §7.2 + FE client fns. Test fetch+list+tree+file+search. Commit (`feat(opensrc): HTTP routes + api client`).

### Task C3: controller tool + policy + persona capability

**Files:** Modify `backend/agentflow/controller_protocol.py` (add `OpensrcAction`), `backend/agentflow/controller/actions.py` (`execute` handles it), `backend/agentflow/policy_service.py` (allow `opensrc path`), `backend/agentflow/orchestrator/personas.py` (capability line); Test `backend/tests/test_controller_opensrc.py`

**Interfaces:** `OpensrcAction = {type:"opensrc", pkg:str, path?:str}` in the `ControllerAction` union.

- [ ] **Step 1 — failing test:** a `clitc_result_v1` block with an `opensrc` action, parsed + executed, fetches source and appends a snippet to the transcript; `policy_service` classifies `opensrc path zod` as allowed.
- [ ] **Step 2 — run, expect fail.** **Step 3 — implement** (both agent paths: controller action + CLI capability line). **Step 4 — green + commit** (`feat(opensrc): controller tool + agent capability`).

### Task C4: SourcesPage + ActivityBar

**Files:** Create `frontend/src/pages/SourcesPage.tsx`; Modify `App.tsx`, `ActivityBar.tsx`; reuse `components/FileTree.tsx` + existing code viewer; Test `frontend/src/test/SourcesPage.test.tsx`

- [ ] **Step 1 — failing vitest:** SourcesPage renders search + fetch; mocked `opensrcTree` populates the reused FileTree; selecting a file shows contents.
- [ ] **Step 2 — run, expect fail.** **Step 3 — implement** (ui-ux-pro-max themed). **Step 4 — green + commit** (`feat(opensrc): Sources browse tab`).

---

# Phase D — cross-cutting

### Task D1: Settings surface for engine tunables

**Files:** Modify `frontend/src/pages/SettingsPage.tsx` (+ any settings route); Test extend settings test.

- [ ] Surface routing/dispatch/fallback highlights (read-only defaults + the few user-editable knobs). Commit (`feat(settings): engine tunables`).

### Task D2: Docs + final verify

**Files:** Modify `README.md`, `DESIGN.md`, `CHANGELOG.md`.

- [ ] Document the rebase, the two tabs, prereqs (`codebase-memory-mcp`, `opensrc`, `AGENTCLI_CORE_PATH`). Run `make verify` — all green. Commit (`docs: orchestrator rebase + memory + opensrc`).

---

## Self-Review (against the spec)

**Spec coverage:** §5 Foundation → A1–A8 ✓ · §6 Memory → B1–B5 ✓ · §7 opensrc → C1–C4 ✓ · §8 cross-cutting (deps/config/testing/safety) → distributed + D1/D2 ✓ · §9 decisions honored in Global Constraints ✓ · §10 risks addressed (loader/snapshot A1, provider map A3, lazy-load B4, fake-binary tests B1/C1) ✓.

**Placeholders:** none — every task names exact files, interfaces, and a concrete failing test.

**Type consistency:** `RouteResult`/`Stage` (A2) consumed by `dispatch_adapter.plan` (A3) → `StagePlan` consumed by `task_service` (A7); `{nodes,edges}` shape defined B1, consumed B2/B4; `OpensrcAction` defined C3 consumed by controller. Names consistent across tasks.
