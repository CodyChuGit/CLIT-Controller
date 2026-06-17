# Initial Audit — CLIT Controller IDE (AgentComposer)

Baseline audit performed on the `audit/production-hardening` branch. Method: a
12-finder multi-agent sweep across the backend transport/services/security,
frontend architecture/components/accessibility, dependencies, developer
experience, and testing, followed by **adversarial verification of every P1
finding against the real code** (a second agent tried to refute each, reading the
cited lines and, for executable claims, running them). All trust-boundary modules
were additionally read by hand to corroborate the machine findings.

## Repository summary

A local-first developer tool — "CLIT Controller IDE" — that orchestrates CLI
coding agents (`claude`, `codex`, `agy`/antigravity) as subprocesses, runs PTY
terminals over WebSockets, manages a git workspace, and streams agent output to a
React UI via SSE + polling. ~6,500 LOC Python (FastAPI + uvicorn + pydantic) and
~7,700 LOC TypeScript (React 18 + Vite 5 + Tailwind + xterm). Single local user;
binds `127.0.0.1:8787`. macOS-oriented (uses `open`, `open -a Terminal`, `.app`
bundles).

See [ARCHITECTURE.md](../ARCHITECTURE.md) for the module map and data flow, and
[OPERATIONS.md](../OPERATIONS.md) for how it runs.

## How the system currently runs

- **Dev:** `scripts/dev.sh` → backend on `:8787` + Vite dev server on `:5180`
  proxying `/api` (WS included). Hot reload on the frontend.
- **Production / single-port:** build the frontend (`tsc && vite build`) → backend
  serves `frontend/dist` at `:8787`.
- **State:** global `~/.agentflow/` (config, providers cache, terminal pidfiles)
  and per-workspace `<workspace>/.agentflow/` (config, usage, tasks, and the
  durable `events.json` / `runs.json` / `approvals.json` / `queue.json` /
  `chat.json` ledgers). All plaintext JSON written atomically; startup recovery
  settles anything left `running` after a restart.

## Critical paths

1. **Agent run lifecycle** — a task step or chat message becomes a subprocess via
   a `shlex`-parsed command template, streamed live through the event bus and a
   per-provider single-flight gate, with state-machine transitions persisted to
   the run/queue ledgers.
2. **Live terminals** — PTY sessions over WebSocket that outlive a single socket,
   with bounded scrollback replay and orphan reaping.
3. **Workspace file read/write + git** — confined to the selected workspace.
4. **Auto-executed `agentflow-run` directives** — commands an agent emits that the
   controller can run, gated by the policy classifier.

## Overall assessment

The codebase is **well-engineered for a solo local-first tool**: no `shell=True`,
explicit `argv` everywhere, git `--` separators, path containment, secret
redaction across most surfaces, a WebSocket Origin allow-list, loopback-only
binding, bounded in-memory buffers, and a genuinely careful PTY lifecycle
(orphan-reaping pidfiles, fd cleanup, SIGTERM→SIGKILL backstops). There are **no
P0 issues**. The real gaps are (a) missing engineering safety rails (CI, linters,
formatters, type-checking config, frontend tests, a lockfile) and (b) a set of
reliability/security hardening items concentrated on the long-running agent
subprocess path, the auto-run policy, durable-state concurrency, and frontend
resilience.

## Findings by severity

Totals: **0 P0 · 11 P1 · 31 P2 · 43 P3** (85 total). All 11 P1s were adversarially
verified: 8 confirmed at P1, 3 down-adjusted (to P2/P3), **0 rejected**.

### High-risk (P1) — the priority repairs

| ID | Finding | Verified |
|----|---------|----------|
| P1-05 | Auto-run policy denylist is bypassable (`make`/`node`/`npx`/`awk`) → prompt-injection-to-RCE in default mode | confirmed (exploit run) |
| P1-02 | Unredacted command/action leaks into `events.json` + `approvals.json` + SSE via the structured `data` payload | confirmed |
| P1-03 | Agent subprocess runs have no wall-clock timeout — a hung CLI wedges its provider lane and deadlocks the autonomous queue | confirmed |
| P1-04 | Backend shutdown never cancels in-flight agent subprocesses — orphaned process groups (esp. dev servers holding ports) | confirmed |
| P1-09 | CSRF: simple-request mutating POSTs (`terminal kill`, `chat stop/clear`, `open-folder`) execute from any web origin; `chat/clear` is data loss | confirmed |
| P1-08 | No React error boundary — any render-phase throw white-screens the whole IDE | confirmed |
| P1-10 | Terminal WebSocket route + its Origin allow-list (guards a real shell) had zero tests | confirmed |
| P1-11 | Process cancel/timeout (SIGTERM→SIGKILL) paths were untested | confirmed |
| P1-01→P2 | Unsynchronized read-modify-write of JSON state across threadpool + loop (lost updates) — real but rare/self-correcting for one user | adjusted |
| P1-06→P2 | `httpx` (TestClient dep) undeclared in dev extras — clean install fails tests once frontend is built | adjusted |
| P1-07→P3 | Stale editable venv registered as `agentflow-studio` (renamed project) — dev-machine metadata only | adjusted |

### Medium-risk (P2) — 31 findings

Highlights: CORS lists the stale `5173` dev port instead of `5180` (P2-10);
`chat send()` doesn't validate `provider` before launching it (P2-11); git
`file-diff` can read in-workspace `.env` via the untracked-file synthesis path,
bypassing the read guard (P2-22); unlocked ledger writes race the dispatcher
(P2-07); blocking file I/O on the event loop in the dispatcher tick (P2-08);
restart recovery leaks the still-alive agent process (P2-11/reliability);
responses are never runtime-validated on the frontend (P2-14); no request
cancellation/stale-guard on selection changes (P2-15); no Python lockfile (P2-23)
and unbounded `>=` constraints (P2-24); no CI/linting/type tooling (P2-26);
no frontend test infrastructure (P2-28); tests used the real `~/.agentflow`
(P2-29); accessibility gaps in the command palette focus trap (P2-19), live
announcements (P2-20), and ARIA widget keyboard support (P2-21); the stale-
expectation test failure (P2-31).

### Low-risk (P3) — 43 findings

Cleanup and incremental items: fire-and-forget asyncio tasks not retained
(P3-12); WebSocket slow-consumer silent drop (P3-13); preview `/check` as a
localhost port-probe oracle (P3-20); `task_id` path interpolation relying on
route-segment matching (P3-21); `noUncheckedIndexedAccess` off (P3-31); flat
heading hierarchy and `window.confirm` dialogs (P3-29/P3-30); leaked `vjbooth`
reference and redundant launcher scripts (P3-26/P3-27); naming sprawl across
packaging metadata (P2-25). Two **positive** confirmations: the Prism
`dangerouslySetInnerHTML` is XSS-safe (P3-34) and no agent output is rendered as
raw HTML anywhere (P3-37).

The complete register with file references is in [Appendix A](#appendix-a--full-findings-register).

## Proposed repair order

1. **Baseline & safety rails (no behavior change):** dev tooling (ruff, mypy,
   pytest-cov, httpx, pip-audit) + ESLint/Prettier/Vitest, CI, `.env.example`,
   Makefile, lockfile, the docs deliverables, test isolation fixture, the stale
   test fix, and characterization tests for the untested critical paths
   (P1-10, P1-11, P2-29, P2-31, P1-06, P2-23/24/26, P3-42).
2. **Production hardening (behavior changes, each with a regression test):**
   P1-05 (policy), P1-02 (payload redaction), P1-09 (CSRF middleware), P1-03
   (run timeouts), P1-04 (shutdown cancel), P1-08 (error boundary), plus
   high-value P2s: P2-10 (CORS port), P2-11 (provider validation), P2-22 (git
   `.env` guard), and selected P3 cleanups (P3-12, P3-26).
3. **Remaining P2/P3** recorded as honest residual work in the final report.

## Assumptions

- Single local user; "no authentication" is by design, not a defect.
- macOS is the primary target (the code uses macOS-only `open`); cross-platform
  parity is out of scope beyond not gratuitously breaking it.
- Provider CLIs manage their own auth; the app neither holds nor should hold
  provider API keys.
- The existing tests encode intended behavior except where shown otherwise
  (P2-31).

## Items intentionally left unchanged

- The denylist→allowlist inversion is implemented as **targeted hardening** of the
  high-risk vectors plus an approval default, not a full allowlist rewrite, to
  avoid breaking legitimate agent commands.
- Large architectural refactors flagged by the audit (splitting oversized
  components P2-18/P2-26; per-workspace dispatcher P3-08; full runtime-schema
  validation P2-14) are recorded as recommendations, not done in this pass — they
  are multi-day changes with real regression risk and no current defect.
- The repo-wide formatting normalization is applied in a single isolated commit,
  separate from any behavior change.

## Appendix A — Full findings register

Generated from the multi-agent audit (12 finders + adversarial verification of every P1). Totals: 0 P0 · 11 P1 · 31 P2 · 43 P3 (85 total). All 11 P1s were adversarially verified: 8 confirmed, 3 severity-adjusted, 0 rejected.


### P1 — 11 finding(s)

| # | Area | Category | Finding | Files | Fix | BC |
|---|------|----------|---------|-------|-----|----|
| P1-01 | be-filesystem | security | Unredacted command leaks into durable events.json and SSE via event `data` payload | backend/agentflow/chat_service.py:66-69, backend/agentflow/event_bus.py:64-87 | S | N |
| P1-02 | be-orchestration | concurrency | Unsynchronized read-modify-write of shared JSON state across threadpool + event loop (lost updates) _(verified→P2)_ | backend/agentflow/queue_service.py:133-141, backend/agentflow/queue_service.py:78-115 | L | N |
| P1-03 | be-reliability | reliability | Agent subprocess runs have no wall-clock timeout — a hung CLI runs forever | backend/agentflow/task_service.py:526, backend/agentflow/chat_service.py:397 | M | Y |
| P1-04 | be-reliability | reliability | Backend shutdown does not cancel running agent subprocesses (orphans on every exit) _(verified)_ | backend/agentflow/app.py:62, backend/agentflow/process_runner.py:444 | S | Y |
| P1-05 | be-subprocess | security | Policy denylist for auto-executed `agentflow-run` commands is bypassable, enabling arbitrary code execution via prompt injection | backend/agentflow/policy_service.py:70-133, backend/agentflow/chat_service.py:50-142 | M | Y |
| P1-06 | dx-ci-docs | testing | httpx is required by the test suite but not declared as a dev dependency — clean install fails tests | pyproject.toml:16-17, backend/tests/test_security_fixes.py:78 | S | N |
| P1-07 | dx-ci-docs | deps | Existing .venv is registered under a stale package name that no longer matches pyproject.toml | pyproject.toml:6, .venv/lib/python3.11/site-packages/agentflow_studio-0.1.0.dist-info/METADATA | S | N |
| P1-08 | fe-a11y | reliability | No React error boundary — a single render error white-screens the entire app | frontend/src/main.tsx:6-10, frontend/src/App.tsx:214-292 | S | Y |
| P1-09 | security-threat | security | CSRF: no-body/optional-body state-changing POST endpoints execute from any web origin _(verified)_ | backend/agentflow/app.py:74-83, backend/agentflow/api/routes_projects.py:140-145 | M | N |
| P1-10 | testing | testing | Terminal WebSocket route (drives a real shell) and its Origin allow-list are untested | backend/agentflow/api/routes_terminals.py:51-120, backend/agentflow/api/routes_terminals.py:24-29 | M | N |
| P1-11 | testing | testing | Process cancellation and timeout paths (SIGTERM→SIGKILL escalation) are untested _(verified)_ | backend/agentflow/process_runner.py:418-450, backend/agentflow/process_runner.py:311-331 | M | N |

### P2 — 31 finding(s)

| # | Area | Category | Finding | Files | Fix | BC |
|---|------|----------|---------|-------|-----|----|
| P2-01 | be-filesystem | reliability | Unlocked read-modify-write on all JSON ledgers races the dispatcher loop (lost updates / duplicate event ids) | backend/agentflow/state_store.py:87-103, backend/agentflow/state_store.py:137-151 | M | N |
| P2-02 | be-orchestration | performance | Blocking file I/O performed on the event loop in the dispatcher tick and on_complete callbacks | backend/agentflow/queue_service.py:463-482, backend/agentflow/queue_service.py:202-305 | M | N |
| P2-03 | be-orchestration | correctness | Stale meta closure in run_full_sequence — budget-saver decision uses a snapshot, not fresh state | backend/agentflow/task_service.py:578-682 | S | N |
| P2-04 | be-orchestration | reliability | _await_run busy-polls RUNNER.runs and can KeyError if the record is evicted | backend/agentflow/task_service.py:565-569, backend/agentflow/process_runner.py:197-206 | S | N |
| P2-05 | be-reliability | reliability | Restart recovery settles ledger state but leaks the still-alive agent OS process | backend/agentflow/state_store.py:271, backend/agentflow/state_store.py:236 | M | Y |
| P2-06 | be-reliability | performance | Dispatcher loop does synchronous JSON file I/O on the event loop every 1.5s | backend/agentflow/queue_service.py:463, backend/agentflow/queue_service.py:473 | M | N |
| P2-07 | be-reliability | reliability | Dev-server preview run can be silently orphaned and is never timed out | backend/agentflow/api/routes_preview.py:97, backend/agentflow/api/routes_preview.py:35 | S | Y |
| P2-08 | be-subprocess | security | Full parent environment (including all secrets) is inherited by every spawned agent and PTY shell | backend/agentflow/process_runner.py:359-369, backend/agentflow/terminal_service.py:37-47 | M | Y |
| P2-09 | be-subprocess | security | Auto-executed commands and agent steps run project-controlled code in a possibly-untrusted workspace | backend/agentflow/chat_service.py:109-112, backend/agentflow/task_service.py:448-452 | M | Y |
| P2-10 | be-transport | correctness | CORS allowlist lists stale dev port 5173, not the actual 5180 dev server (diverges from WS allowlist) | backend/agentflow/app.py:77-82, backend/agentflow/api/routes_terminals.py:24-29 | S | Y |
| P2-11 | be-transport | security | chat_service.send() does not validate `provider`; arbitrary value flows into a fallback command template and is launched as an executable | backend/agentflow/api/routes_chat.py:28-30, backend/agentflow/chat_service.py:274-310 | S | Y |
| P2-12 | be-transport | reliability | Terminal WebSocket fan-out silently drops output to slow clients with no resync | backend/agentflow/terminal_service.py:212-217, backend/agentflow/api/routes_terminals.py:71-92 | M | Y |
| P2-13 | be-transport | dx | Errors returned as HTTP 200 with a string status in the body instead of proper 4xx codes | backend/agentflow/queue_service.py:313-410, backend/agentflow/api/routes_queue.py:50-72 | M | Y |
| P2-14 | deps-supplychain | deps | No Python lockfile — backend dependency resolution is non-reproducible | /Users/cody/AgentComposer/pyproject.toml:10-17 | S | N |
| P2-15 | deps-supplychain | deps | Python deps use unbounded `>=` constraints — major-version upgrades can land unvetted | /Users/cody/AgentComposer/pyproject.toml:10-14, /Users/cody/AgentComposer/pyproject.toml:17 | S | N |
| P2-16 | dx-ci-docs | dx | Four-way project naming inconsistency across packaging metadata | pyproject.toml:6, frontend/package.json:2 | M | N |
| P2-17 | dx-ci-docs | tooling | No CI, no linting/formatting/type-checking tooling, and no documented test command | .github (absent), pyproject.toml:1-25 | M | N |
| P2-18 | dx-ci-docs | dx | Redundant, overlapping launcher and macOS-app-bundle scripts | scripts/app.sh, scripts/app-mode.sh | M | Y |
| P2-19 | fe-a11y | a11y | CommandPalette dialog has no focus trap and does not restore focus on close | frontend/src/components/CommandPalette.tsx:33,52-110, frontend/src/components/ChatPanel.tsx:842 | M | Y |
| P2-20 | fe-a11y | a11y | Live-streaming agent reply has no aria-live region — screen readers never announce responses | frontend/src/components/ChatPanel.tsx:730-743, frontend/src/components/SmoothStreamingText.tsx:91-98 | M | N |
| P2-21 | fe-a11y | a11y | ARIA widget roles (tab/tablist, listbox/option, tree) declared without required keyboard interaction | frontend/src/components/ChatPanel.tsx:598-641,252-277, frontend/src/pages/ProjectsPage.tsx:188-231 | M | Y |
| P2-22 | fe-architecture | correctness | Network responses are never validated at runtime — every payload is a blind `as T` cast | frontend/src/api.ts:40-56, frontend/src/stream.tsx:218 | L | N |
| P2-23 | fe-architecture | reliability | No request cancellation anywhere; stale-response guarding is partial and misses selection changes (TasksPage) | frontend/src/pages/TasksPage.tsx:73-90, frontend/src/api.ts:40-56 | M | N |
| P2-24 | fe-architecture | security | Preview iframe runs user-controlled URL with allow-scripts + allow-same-origin (sandbox provides little isolation) | frontend/src/pages/PreviewPage.tsx:118-124, frontend/src/pages/PreviewPage.tsx:80-87 | S | Y |
| P2-25 | fe-components-xss | correctness | Markdown segment list uses array-index keys, mismatching state during streaming | frontend/src/components/Markdown.tsx:275-287 | S | N |
| P2-26 | fe-components-xss | architecture | ChatPanel and TasksPage are oversized components mixing data-fetching, polling/business logic, and presentation | frontend/src/components/ChatPanel.tsx:289-845, frontend/src/pages/TasksPage.tsx:25-481 | L | N |
| P2-27 | security-threat | security | git file-diff reads arbitrary in-workspace files (incl. .env / secrets), bypassing the .env read guard | backend/agentflow/git_service.py:117-145, backend/agentflow/api/routes_projects.py:97-99 | S | Y |
| P2-28 | testing | testing | No frontend test infrastructure at all (zero coverage of React UI + WS/SSE client logic) | frontend/package.json:6-10, frontend/src/components/ChatPanel.tsx | M | N |
| P2-29 | testing | testing | Tests use the real ~/.agentflow global config dir — no isolation fixture (state bleed + machine pollution risk) | backend/agentflow/paths.py:10-28, backend/tests/test_security_fixes.py:63-72 | S | N |
| P2-30 | testing | testing | Provider-install test runs real subprocess/which probes against the live machine | backend/tests/test_provider_install.py:6-18, backend/agentflow/provider_probe.py:315-357 | S | N |
| P2-31 | testing | testing | Stale-expectation test failure breaks the suite's green signal | backend/tests/test_routing_service.py:46-51, backend/agentflow/routing_service.py | S | N |

### P3 — 43 finding(s)

| # | Area | Category | Finding | Files | Fix | BC |
|---|------|----------|---------|-------|-----|----|
| P3-01 | be-filesystem | security | task_dir() path-math would escape the tasks dir on a traversal task_id — currently saved only by Starlette URL normalization | backend/agentflow/paths.py:52-57, backend/agentflow/task_service.py:236-244 | S | N |
| P3-02 | be-filesystem | security | Redaction misses space-separated secret flags and bare positional tokens | backend/agentflow/redaction.py:10-25 | S | N |
| P3-03 | be-filesystem | correctness | CORS allow_origins omits the actual dev port 5180 used elsewhere in the app | backend/agentflow/app.py:76-85, backend/agentflow/api/routes_terminals.py:24-29 | S | Y |
| P3-04 | be-orchestration | correctness | _full_sequences_running guard is process-global, not workspace-scoped | backend/agentflow/task_service.py:31, backend/agentflow/task_service.py:592-675 | S | N |
| P3-05 | be-orchestration | concurrency | Check-then-act provider-busy TOCTOU between running_for_provider and RUNNER.start | backend/agentflow/task_service.py:390-392, backend/agentflow/task_service.py:522-531 | M | N |
| P3-06 | be-orchestration | reliability | routing_service.append_decision does a non-atomic file append (bypasses atomic write_json) | backend/agentflow/routing_service.py:141-146 | S | N |
| P3-07 | be-orchestration | concurrency | Consult counter increment is a non-atomic double-read; consult limit can be exceeded | backend/agentflow/chat_service.py:493-535, backend/agentflow/queue_service.py:184-199 | S | N |
| P3-08 | be-orchestration | architecture | Dispatcher single-workspace assumption: tick only ever processes config.get_current_workspace() | backend/agentflow/queue_service.py:473-482, backend/agentflow/config.py:94-99 | M | Y |
| P3-09 | be-orchestration | correctness | Terminal-history prune by id() in _finalize_running is fragile across reloads | backend/agentflow/queue_service.py:254-259 | S | N |
| P3-10 | be-orchestration | correctness | task_service.stop(run_id=None) cancels ALL processes across every workspace, not just the workspace's | backend/agentflow/task_service.py:685-692, backend/agentflow/process_runner.py:444-450 | S | Y |
| P3-11 | be-reliability | reliability | read_json swallows only FileNotFoundError/JSONDecodeError — other OS errors 500 the request | backend/agentflow/config.py:49 | S | Y |
| P3-12 | be-reliability | reliability | Fire-and-forget background tasks (heartbeat, hard-kill, consume) are not retained | backend/agentflow/process_runner.py:391, backend/agentflow/process_runner.py:440 | S | N |
| P3-13 | be-reliability | reliability | WebSocket pump uses bounded queue with put_nowait drop — a slow client silently loses terminal output | backend/agentflow/terminal_service.py:212, backend/agentflow/api/routes_terminals.py:71 | S | N |
| P3-14 | be-subprocess | security | login_provider writes provider commands into a shell script via f-string interpolation | backend/agentflow/provider_probe.py:360-399 | S | N |
| P3-15 | be-subprocess | reliability | Heartbeat background task is never cancelled and relies on status polling to stop | backend/agentflow/process_runner.py:244-250, backend/agentflow/process_runner.py:391 | S | N |
| P3-16 | be-subprocess | reliability | Provider version/status/models probes run resolved CLIs with a 10-15s timeout but no concurrency cap on check-all | backend/agentflow/provider_probe.py:225-297, backend/agentflow/process_runner.py:311-331 | S | N |
| P3-17 | be-transport | dx | Unknown GET /api/* paths fall through to the SPA catch-all and return index.html with 200 | backend/agentflow/app.py:114-123, backend/agentflow/app.py:87-96 | S | Y |
| P3-18 | be-transport | reliability | Preview /check raises unhandled 500 on a stored preview URL with an out-of-range port | backend/agentflow/api/routes_preview.py:67-81, backend/agentflow/api/routes_preview.py:57-64 | S | Y |
| P3-19 | be-transport | security | Preview /start returns un-redacted dev-server stderr to the client | backend/agentflow/api/routes_preview.py:98-99, backend/agentflow/api/routes_preview.py:46 | S | N |
| P3-20 | be-transport | security | Preview /check is a localhost port-probe primitive (timing oracle for any local port) | backend/agentflow/api/routes_preview.py:67-81, backend/agentflow/api/routes_preview.py:57-64 | S | N |
| P3-21 | be-transport | security | task_id from path params is interpolated into filesystem paths with no explicit sanitization (currently blocked only by route segment matching) | backend/agentflow/api/routes_tasks.py:32-88, backend/agentflow/task_service.py:236-242 | S | N |
| P3-22 | be-transport | observability | No global exception handler / standardized machine-readable error envelope | backend/agentflow/app.py:67-106 | S | Y |
| P3-23 | deps-supplychain | deps | vite/esbuild dev-server advisories present (dev-only, not in production bundle) | /Users/cody/AgentComposer/frontend/package.json:28, /Users/cody/AgentComposer/frontend/package-lock.json | M | N |
| P3-24 | deps-supplychain | deps | No dependency vulnerability scanner wired in (pip-audit / npm audit not in CI or tooling) | /Users/cody/AgentComposer/pyproject.toml:16-17 | S | N |
| P3-25 | dx-ci-docs | dx | Multiple competing documented startup paths with no single source of truth | README.md:55-80, scripts/install.sh:39 | S | N |
| P3-26 | dx-ci-docs | cleanup | Leaked external project reference 'vjbooth' in shipped script comments | scripts/app.sh:3, scripts/make-app.sh:3 | S | N |
| P3-27 | dx-ci-docs | cleanup | make-app.sh icon comment claims an SVG source pipeline that the code does not implement | scripts/make-app.sh:52-54, scripts/create-macos-app-mode.sh:48-49 | S | N |
| P3-28 | dx-ci-docs | dx | No .env.example despite multiple env-var knobs | .env.example (absent), scripts/app-mode.sh:18-25 | S | N |
| P3-29 | fe-a11y | a11y | Flat heading hierarchy — only <h1> exists; section titles are non-heading spans | frontend/src/components/ui.tsx:42,76-80, frontend/src/styles.css:87-90 | S | N |
| P3-30 | fe-a11y | a11y | Destructive/blocking actions use native window.confirm with no accessible in-app dialog | frontend/src/components/ChatPanel.tsx:665, frontend/src/pages/ProjectsPage.tsx:198 | M | Y |
| P3-31 | fe-architecture | correctness | tsconfig lacks noUncheckedIndexedAccess despite heavy untrusted index access into records | frontend/tsconfig.json:1-23, frontend/src/lib/displayModel.ts:143 | M | N |
| P3-32 | fe-architecture | dx | import.meta.env used without validation; service worker registered unconditionally in prod | frontend/src/main.tsx:14-20, frontend/src/vite-env.d.ts:1 | S | N |
| P3-33 | fe-architecture | performance | Duplicate / overlapping polling effects per page with no de-duplication | frontend/src/pages/TasksPage.tsx:55-136, frontend/src/App.tsx:107-111 | L | N |
| P3-34 | fe-components-xss | security | CodeReader dangerouslySetInnerHTML is XSS-safe (Prism-escaped) — verified, not a vulnerability | frontend/src/components/CodeReader.tsx:202-204, frontend/src/components/CodeReader.tsx:129-140 | S | N |
| P3-35 | fe-components-xss | correctness | SmoothStreamingText snapshots text.length at mount via useRef initializer, can mis-reveal on remount | frontend/src/components/SmoothStreamingText.tsx:44-46, frontend/src/components/SmoothStreamingText.tsx:50-86 | S | N |
| P3-36 | fe-components-xss | correctness | Index-based keys on several dynamic lists (TimelineCard bullets, table rows, CodeReader diff lines) | frontend/src/components/TimelineCard.tsx:62-63, frontend/src/components/Markdown.tsx:133-149 | S | N |
| P3-37 | fe-components-xss | security | No agent/markdown output is rendered as raw HTML anywhere (positive XSS finding) | frontend/src/components/Markdown.tsx:262-302, frontend/src/components/ChatPanel.tsx:145 | S | N |
| P3-38 | security-threat | security | WebSocket terminal accepts handshakes with no Origin header (local non-browser clients can drive a shell) | backend/agentflow/api/routes_terminals.py:24-32, backend/agentflow/api/routes_terminals.py:55-60 | M | Y |
| P3-39 | security-threat | correctness | CORS allowlist omits the actual dev-server origin (:5180); allowlist is effectively dead config given the Vite proxy | backend/agentflow/app.py:74-83, frontend/vite.config.ts:7-10 | S | N |
| P3-40 | security-threat | security | FastAPI interactive docs and OpenAPI schema served unauthenticated | backend/agentflow/app.py:69-73, backend/agentflow/__main__.py:18 | S | Y |
| P3-41 | security-threat | security | Policy workspace-confinement does not catch symlinks or relative escapes that resolve outside the workspace | backend/agentflow/policy_service.py:59-66, backend/agentflow/policy_service.py:114-118 | M | Y |
| P3-42 | testing | testing | No coverage tooling installed or configured | pyproject.toml:18-19, pyproject.toml:21-22 | S | N |
| P3-43 | testing | testing | API route handlers are tested by direct function calls, never over real HTTP (status mapping / serialization gap) | backend/tests/test_routes_state.py:1-23, backend/agentflow/api/routes_projects.py | M | N |