# Limitations

Honest, material limitations of CLIT Controller IDE (AgentComposer) as it stands
today. This is a curated list of consequential gaps — not an unfiltered TODO dump.
Each entry gives the impact, the current workaround, the residual risk, a
suggested direction, the source paths, and whether it blocks production.

Scope reminder: this is a **local-first, single-user, loopback-only macOS
cockpit**. Several entries below are deliberate design choices for that scope, not
defects. The provenance for most items is the audit and the partial (◐) pillar
acceptance criteria:

- [docs/audit/INITIAL_AUDIT.md](audit/INITIAL_AUDIT.md) — full findings register.
- [docs/audit/FINAL_REPORT.md](audit/FINAL_REPORT.md) §15 — remaining risks.
- [docs/PILLARS.md](PILLARS.md) — the ◐ partial acceptance criteria.

Cross-references: threat model and accepted security risks in
[docs/SECURITY.md](SECURITY.md); architecture and data flow in
[docs/ARCHITECTURE.md](ARCHITECTURE.md); the auto-run policy decision in
[docs/adr/0001-auto-run-policy-allowlist.md](adr/0001-auto-run-policy-allowlist.md).

**Blocks production?** is answered for the product's actual deployment model
(one developer, one machine, loopback). "No" can still mean "fix before any
multi-user or networked deployment" — that case is called out per entry.

---

## Product

### Headroom token/latency metrics are a contract, not a surface

- **Description:** Per-run token-efficiency metrics (context-prep latency,
  time-to-first-token, original vs optimized tokens) are defined as a versioned
  `TokenEfficiencyReport` contract, but there is no dashboard that surfaces them.
  Unmeasured savings are reported as `null` rather than fabricated.
- **Impact:** Users cannot see realized Headroom savings in-app; they must run
  `headroom agent-savings --check-perf` out of band.
- **Workaround:** Use the Headroom CLI directly; treat the in-app report as a
  schema placeholder.
- **Risk:** Low — purely a missing read-only view.
- **Direction:** Render the `TokenEfficiencyReport` in a metrics panel.
- **Source:** [contracts.py](../backend/agentflow/contracts.py),
  [headroom_service.py](../backend/agentflow/headroom_service.py); Pillar 1 ◐ in
  [PILLARS.md](PILLARS.md).
- **Blocks production?** No.

### Orchestrator emits markdown directive blocks, not native structured output

- **Description:** The controller still emits action directives as fenced markdown
  blocks (` ```agentflow-run `, done/needs-user/task/queue blocks) which are then
  parsed and bridged to versioned records. It does not use a provider's native
  structured-output mode.
- **Impact:** Directive extraction depends on the model honoring a markdown
  convention; a malformed or omitted fence is silently a no-op rather than a typed
  validation error at the source.
- **Workaround:** `controller_directive_records` validates the parsed result
  against the Pillar 5 contracts, so a bad payload fails safely (structured
  `FailureRecord`, no crash, no correction loop).
- **Risk:** Medium for correctness of agent control flow; low for safety.
- **Direction:** Move to provider structured-output / tool-call mode for
  directives, keeping the contract validator as the boundary.
- **Source:** [chat_directives.py](../backend/agentflow/chat_directives.py)
  (`RUN_DIRECTIVE_RE`, `controller_directive_records`),
  [contracts.py](../backend/agentflow/contracts.py); Pillar 5 ◐ in
  [PILLARS.md](PILLARS.md).
- **Blocks production?** No.

---

## Frontend

### No full runtime validation of backend responses beyond StreamEvent

- **Description:** The event stream is validated at the boundary
  (`coerceStreamEvent`), but ordinary REST responses are returned as a blind
  `res.json() as Promise<T>` cast with no schema check.
- **Impact:** A backend shape change or an unexpected payload surfaces as a
  downstream render error rather than a clear validation failure at the fetch site.
- **Workaround:** The `ErrorBoundary` (app-wide, per-view, and around ChatPanel)
  contains the blast radius to a recoverable error state instead of a white screen.
- **Risk:** Medium — silent shape drift between backend and frontend.
- **Direction:** Introduce runtime validation (e.g. zod) at the `api.ts`
  boundary, extending the pattern already used for the `StreamEvent` path.
- **Source:** [api.ts](../frontend/src/api.ts) (`res.json() as Promise<T>`),
  [lib/streamEvent.ts](../frontend/src/lib/streamEvent.ts) (`coerceStreamEvent`);
  audit P2-14, FINAL_REPORT §15.
- **Blocks production?** No.

### Oversized components (ChatPanel, TasksPage)

- **Description:** `ChatPanel.tsx` (~980 lines) and `TasksPage.tsx` (~525 lines)
  mix data fetching, polling/business logic, and presentation in single files.
- **Impact:** Higher change risk and review cost; harder to unit-test the logic in
  isolation.
- **Workaround:** Shared primitives (`Markdown`, `TimelineCard`, `displayModel`,
  `useAutoScroll`) already factor out the rendering and projection concerns, so the
  bloat is in orchestration glue, not duplicated rendering.
- **Risk:** Medium for maintainability; no active defect.
- **Direction:** Extract data/polling logic into hooks; keep components
  presentational.
- **Source:** [ChatPanel.tsx](../frontend/src/components/ChatPanel.tsx),
  [TasksPage.tsx](../frontend/src/pages/TasksPage.tsx); audit P2-18/P2-26.
- **Blocks production?** No.

### Auto-scroll hook not adopted at all call sites

- **Description:** `useAutoScroll` (follow-near-bottom + new-output affordance,
  with a pure tested core) exists but is **not imported by any production
  component** — only by its own test. Streaming surfaces still use their own
  scroll handling, and `prefers-reduced-motion` is honored in `SmoothStreamingText`
  but not audited on every surface.
- **Impact:** Scroll behavior is not yet uniform across the Agent Dock, ChatPanel,
  provider chats, task replay, and approval views (Pillar 4 consistency goal).
- **Workaround:** Existing per-surface scroll logic works; the shared hook is the
  intended consolidation target.
- **Risk:** Low — UX inconsistency, not a functional defect.
- **Direction:** Adopt `useAutoScroll` at the remaining legacy scroll call sites
  and audit reduced-motion handling on each.
- **Source:** [hooks/useAutoScroll.ts](../frontend/src/hooks/useAutoScroll.ts)
  (unreferenced in `src/` outside its test),
  [SmoothStreamingText.tsx](../frontend/src/components/SmoothStreamingText.tsx);
  Pillar 4 ◐ in [PILLARS.md](PILLARS.md).
- **Blocks production?** No.

### CLI output normalization beyond ANSI is partial

- **Description:** ANSI escape sequences are stripped from prose log/stdout/stderr
  views, but higher-level CLI normalization — classifying compiler / test runner /
  linter output into a single structured Command surface — is not implemented.
- **Impact:** Tool output is readable but not consistently summarized into typed
  command/test result cards; the user still scans raw lines for some tools.
- **Workaround:** `RawDetail` paginates raw output behind expanders;
  `displayModel` maps known event kinds to cards.
- **Risk:** Low.
- **Direction:** Add per-tool output classifiers feeding the existing command/test
  summary contracts.
- **Source:** [lib/ansi.ts](../frontend/src/lib/ansi.ts),
  [lib/displayModel.ts](../frontend/src/lib/displayModel.ts),
  [components/RawDetail.tsx](../frontend/src/components/RawDetail.tsx); Pillar 3 ◐
  in [PILLARS.md](PILLARS.md).
- **Blocks production?** No.

---

## Backend

### Blocking file I/O on the asyncio event loop

- **Description:** The dispatcher `tick` and its completion callbacks perform
  synchronous JSON reads/writes (`config.read_json` / `config.write_json`) directly
  on the event loop, roughly every `TICK_SECONDS`. There is no `run_in_executor`,
  `asyncio.to_thread`, or async file I/O anywhere in the services layer.
- **Impact:** Under a slow disk or a large ledger, a tick can stall the loop and
  briefly delay SSE delivery and request handling — at odds with the live-output
  invariant.
- **Workaround:** Ledgers are small for a single user and writes are atomic
  (tmp + `os.replace`), so stalls are short in practice.
- **Risk:** Medium for responsiveness as ledgers grow; low for correctness.
- **Direction:** Offload ledger I/O off the loop (thread executor or async file
  I/O), starting with the dispatcher tick.
- **Source:** [queue_service.py](../backend/agentflow/queue_service.py) (`tick`,
  `dispatcher_loop`), [config.py](../backend/agentflow/config.py)
  (`read_json`/`write_json`); audit P2-02/P2-06/P2-08, FINAL_REPORT §15.
- **Blocks production?** No.

---

## API

### Some errors returned as HTTP 200 with a status string in the body

- **Description:** Parts of the queue/dispatch path return a string status in a 200
  body instead of mapping failures to 4xx/5xx codes, and there is no global
  exception handler emitting a standardized machine-readable error envelope.
- **Impact:** Clients must inspect the body to detect failures; status codes are
  not a reliable signal. Frontend handling already tolerates this, but it
  complicates any future API consumer.
- **Workaround:** Frontend reads the body status; behavior is consistent within
  the app.
- **Risk:** Low for this app; medium if the API is consumed by other clients.
- **Direction:** Map domain errors to proper status codes and add a global
  exception handler with a typed error envelope.
- **Source:** [queue_service.py](../backend/agentflow/queue_service.py),
  [api/routes_queue.py](../backend/agentflow/api/routes_queue.py),
  [app.py](../backend/agentflow/app.py); audit P2-13/P3-22.
- **Blocks production?** No (single-app consumer).

---

## Persistence

### Unsynchronized read-modify-write of the JSON ledgers (top remaining item)

- **Description:** The durable JSON ledgers (`events.json`, `runs.json`,
  `queue.json`, `approvals.json`) are read-modify-written without a lock across the
  threadpool and the event loop. Individual writes are atomic (tmp + `os.replace`),
  but a concurrent read-modify-write can lose an update or duplicate an event id.
- **Impact:** Rare lost updates or duplicate ids under concurrent activity (e.g.
  the dispatcher writing while a request handler also writes).
- **Workaround:** Largely self-correcting for a single user; the workloads that
  collide are infrequent, and atomic writes prevent torn files.
- **Risk:** Medium — this is the highest-priority remaining correctness item.
- **Direction:** Add a per-workspace lock around ledger read-modify-write.
- **Source:** [state_store.py](../backend/agentflow/state_store.py)
  (`append_event` and the `write_json` callers),
  [config.py](../backend/agentflow/config.py) (`write_json`),
  [queue_service.py](../backend/agentflow/queue_service.py); audit P1-01/P2-01/P2-07,
  FINAL_REPORT §15.
- **Blocks production?** No for single-user; **yes** for any concurrent/multi-user
  deployment.

### No database — plaintext JSON only

- **Description:** All state is plaintext JSON under `~/.agentflow/` (global) and
  `<workspace>/.agentflow/` (per-workspace). No transactional store, no indexes.
- **Impact:** No multi-process transactional guarantees; large histories are
  whole-file rewrites; querying is linear scans.
- **Workaround:** Cursor-resumable event ledger and bounded buffers keep working
  sets small; startup recovery settles interrupted state.
- **Risk:** Low at single-user scale; grows with history size.
- **Direction:** Keep JSON for the local model; consider an embedded store only if
  scale demands it.
- **Source:** [state_store.py](../backend/agentflow/state_store.py),
  [paths.py](../backend/agentflow/paths.py),
  [config.py](../backend/agentflow/config.py); [ARCHITECTURE.md](ARCHITECTURE.md).
- **Blocks production?** No (design choice for local-first).

---

## Performance

### Single-workspace dispatcher

- **Description:** The dispatcher loop only ever processes
  `config.get_current_workspace()` per tick.
- **Impact:** Queued steps in non-current workspaces are not advanced until that
  workspace is selected.
- **Workaround:** Switch the current workspace; the single-user model means one
  active workspace at a time is the normal case.
- **Risk:** Low for the intended usage.
- **Direction:** Per-workspace dispatchers if concurrent multi-workspace
  autonomy is needed.
- **Source:** [queue_service.py](../backend/agentflow/queue_service.py)
  (`dispatcher_loop`); audit P3-08.
- **Blocks production?** No.

### WebSocket terminal fan-out drops output to slow clients

- **Description:** The terminal pump uses a bounded queue with `put_nowait`; a slow
  consumer silently loses output with no resync.
- **Impact:** A lagging terminal viewer can miss bytes; scrollback replay mitigates
  reconnects but not in-session drops.
- **Workaround:** Bounded scrollback replay on reconnect restores recent context.
- **Risk:** Low — affects display fidelity, not the underlying shell.
- **Direction:** Backpressure or a resync cursor for the terminal stream.
- **Source:** [terminal_service.py](../backend/agentflow/terminal_service.py),
  [api/routes_terminals.py](../backend/agentflow/api/routes_terminals.py); audit
  P2-12/P3-13.
- **Blocks production?** No.

---

## Reliability

### Crash-time agent-process orphaning

- **Description:** Clean shutdown cancels in-flight runs (`RUNNER.cancel_all()` in
  the lifespan hook). A hard crash (SIGKILL / power loss) skips that hook, and
  restart recovery settles the ledger to `failed` but never signals the
  still-alive OS process.
- **Impact:** After a hard crash, an agent or dev-server process group can survive
  and hold ports/resources while the UI shows the run as failed.
- **Workaround:** Kill leftover processes manually (e.g. by port or process name)
  after an abnormal exit; clean shutdowns are fully covered.
- **Risk:** Medium — resource/port leak after abnormal exit.
- **Direction:** Record child pids/process-group ids durably and reap them
  (pid-reuse-safe) during restart recovery.
- **Source:** [app.py](../backend/agentflow/app.py) (lifespan `cancel_all`),
  [state_store.py](../backend/agentflow/state_store.py) (recovery settles ledger,
  no process signal), [process_runner.py](../backend/agentflow/process_runner.py);
  audit P2-05, FINAL_REPORT §15.
- **Blocks production?** No (recoverable manually); fix recommended.

---

## Security

> The full threat model and the explicitly accepted risks live in
> [SECURITY.md](SECURITY.md). The two items below are the ones most likely to
> surprise someone evaluating the tool.

### Single-user, no authentication (by design)

- **Description:** The backend binds `127.0.0.1:8787` and has no auth. Anyone with
  loopback access to the machine can drive it. FastAPI `/docs` and the OpenAPI
  schema are served unauthenticated.
- **Impact:** The tool is only as isolated as the host. It is not safe to expose on
  a network or to untrusted local users.
- **Workaround:** Run only on a trusted single-user machine; do not port-forward or
  bind to a non-loopback interface.
- **Risk:** High **if** the loopback assumption is violated; otherwise accepted.
- **Direction:** Authentication/authorization would be required before any
  non-loopback or multi-user deployment.
- **Source:** [app.py](../backend/agentflow/app.py),
  [origins.py](../backend/agentflow/origins.py); audit P3-40, SECURITY.md.
- **Blocks production?** No for local-first; **yes** for any networked/multi-user
  deployment.

### WebSocket terminal accepts handshakes with no Origin header

- **Description:** The terminal WebSocket enforces an Origin allow-list for
  browser clients but accepts handshakes that send no Origin header at all, so a
  local non-browser client can drive a real shell.
- **Impact:** Any local process can open a PTY over the WS endpoint, bypassing the
  browser-origin check.
- **Workaround:** Loopback-only binding limits this to local processes, which
  already have shell access on the machine.
- **Risk:** Low under the single-user loopback model; documented as accepted.
- **Direction:** Require a same-origin token for WS handshakes if the loopback
  assumption is ever relaxed.
- **Source:** [api/routes_terminals.py](../backend/agentflow/api/routes_terminals.py),
  [origins.py](../backend/agentflow/origins.py); audit P3-38, SECURITY.md §15.
- **Blocks production?** No for local-first; revisit for networked deployment.

---

## Accessibility

### No focus trap / focus restoration in the command palette

- **Description:** The command palette dialog has no focus trap and does not
  restore focus to the trigger on close.
- **Impact:** Keyboard and screen-reader users can tab out of the open dialog and
  lose their place.
- **Workaround:** Mouse users are unaffected; the dialog still functions.
- **Risk:** Medium for keyboard/AT users.
- **Direction:** Add a focus trap and restore focus on close.
- **Source:** [components/CommandPalette.tsx](../frontend/src/components/CommandPalette.tsx),
  [ChatPanel.tsx](../frontend/src/components/ChatPanel.tsx); audit P2-19.
- **Blocks production?** No.

### Streaming replies have no `aria-live` region

- **Description:** The live-streaming agent reply is not wrapped in an `aria-live`
  region, so screen readers never announce incoming responses.
- **Impact:** Screen-reader users do not hear streamed output as it arrives.
- **Workaround:** None in-app.
- **Risk:** Medium for AT users.
- **Direction:** Wrap the streaming reply in a polite `aria-live` region.
- **Source:** [ChatPanel.tsx](../frontend/src/components/ChatPanel.tsx),
  [SmoothStreamingText.tsx](../frontend/src/components/SmoothStreamingText.tsx);
  audit P2-20.
- **Blocks production?** No.

### ARIA widget roles without full keyboard interaction

- **Description:** `tab`/`tablist`, `listbox`/`option`, and tree roles are declared
  in the UI without the required keyboard interaction (arrow-key navigation,
  selection), and some destructive/blocking actions use native `window.confirm`
  instead of an accessible in-app dialog.
- **Impact:** Widgets announce a role they do not fully support via keyboard;
  `window.confirm` dialogs are not styled or trapped consistently.
- **Workaround:** Mouse interaction works; confirmations still block the action.
- **Risk:** Medium for keyboard/AT users.
- **Direction:** Implement the keyboard contracts for the declared roles; replace
  `window.confirm` with an accessible modal.
- **Source:** [ChatPanel.tsx](../frontend/src/components/ChatPanel.tsx)
  (`role="listbox"`, `role="tab"`, `window.confirm`),
  [pages/ProjectsPage.tsx](../frontend/src/pages/ProjectsPage.tsx); audit
  P2-21/P3-30.
- **Blocks production?** No.

---

## Testing

### No Playwright / end-to-end coverage

- **Description:** There is no Playwright (or Cypress) e2e suite. Coverage is
  backend pytest plus frontend Vitest unit/component tests. API route handlers are
  largely tested by direct function calls rather than over real HTTP.
- **Impact:** Integration paths spanning browser → SSE/WS → backend → subprocess
  are not exercised end to end; HTTP status-mapping and serialization gaps can slip
  through.
- **Workaround:** Backend WebSocket gating and process cancel/timeout paths have
  targeted tests; the StreamEvent path is unit-tested.
- **Risk:** Medium — no automated full-stack regression signal.
- **Direction:** Add a small Playwright suite for the critical live-output and
  terminal flows; add HTTP-level route tests.
- **Source:** `frontend/` (no e2e config present),
  [backend/tests/](../backend/tests/); audit P3-43.
- **Blocks production?** No.

---

## Deployment

### macOS-only operating-system integration

- **Description:** OS integration uses macOS-only `open` / `open -a Terminal`, and
  the packaging assumes `.app` bundles.
- **Impact:** "Open folder", "open in Terminal", provider login launch, and the
  app-bundle launchers do not work on Linux/Windows.
- **Workaround:** Run on macOS; the HTTP/WS core is OS-agnostic but these affordances
  are not.
- **Risk:** Low within the stated target (macOS).
- **Direction:** Abstract the OS-open layer if cross-platform support is pursued.
- **Source:** [api/routes_tasks.py](../backend/agentflow/api/routes_tasks.py)
  (`open`), [api/routes_projects.py](../backend/agentflow/api/routes_projects.py)
  (`open`), [provider_probe.py](../backend/agentflow/provider_probe.py)
  (`open -a Terminal`), [scripts/](../scripts/); INITIAL_AUDIT assumptions.
- **Blocks production?** No for macOS target; **yes** for other platforms.

---

## DX

### Dev-only `vite` / `esbuild` advisory

- **Description:** Known `vite`/`esbuild` dev-server advisories are present. They
  affect the dev server only and are **not** in the production bundle (`npm audit`
  on production deps reports 0 vulnerabilities).
- **Impact:** None at runtime for built output; relevant only to the local dev
  server.
- **Workaround:** None needed for production builds; keep the dev server on
  loopback.
- **Risk:** Low — dev-only, fix requires a breaking Vite major upgrade.
- **Direction:** Upgrade Vite when ready to absorb the major-version break.
- **Source:** [frontend/package.json](../frontend/package.json),
  [frontend/package-lock.json](../frontend/package-lock.json); audit P3-23,
  FINAL_REPORT §15.
- **Blocks production?** No.
