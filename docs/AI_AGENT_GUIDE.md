# AI Agent Guide — deterministic handoff

This file is the orientation for a future coding agent picking up work in this
repository. It is intentionally redundant with the short
["AI agent handoff" section of DEVELOPMENT.md](DEVELOPMENT.md#ai-agent-handoff);
this is the long form. Read the linked sources before writing code — do not infer
behavior from this page alone.

The product is **CLIT Controller IDE** (also "AgentComposer" at the repo root): a
local-first, single-user developer cockpit that orchestrates CLI coding agents
(`claude`, `codex`, `agy`/antigravity) as subprocesses, runs PTY terminals over
WebSockets, manages a git workspace, and streams agent output live. It binds the
loopback interface only and has no authentication by design.

## 1. Read these first (in order)

1. [docs/PILLARS.md](PILLARS.md) — the five product pillars and the interaction
   model. This defines what "good" means; every change is judged against it.
2. [docs/ARCHITECTURE.md](ARCHITECTURE.md) — how backend, frontend, and the event
   stream fit together.
3. [docs/ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md) — the enforced
   invariants and the one verification command surface.
4. [backend/agentflow/contracts.py](../backend/agentflow/contracts.py) — the
   versioned, `kind`-discriminated semantic layer (Pillar 5).
5. [backend/agentflow/event_bus.py](../backend/agentflow/event_bus.py) — the
   canonical live event stream.
6. [backend/agentflow/process_runner.py](../backend/agentflow/process_runner.py) —
   how subprocesses are spawned, read incrementally, redacted, and finalized.

Supporting reads when relevant: [docs/SECURITY.md](SECURITY.md),
[docs/OPERATIONS.md](OPERATIONS.md),
[docs/adr/0001-auto-run-policy-allowlist.md](adr/0001-auto-run-policy-allowlist.md),
[docs/audit/INITIAL_AUDIT.md](audit/INITIAL_AUDIT.md), and
[docs/audit/FINAL_REPORT.md](audit/FINAL_REPORT.md).

## 2. Architectural invariants (do not violate)

These are the load-bearing rules. A change that breaks one is wrong even if tests
pass; if you believe one must change, that is a documented, justified decision, not
a side effect.

- **The canonical event stream is the single source of operational truth.** All live
  output flows through [event_bus.py](../backend/agentflow/event_bus.py) (in-memory
  ring buffer, monotonic ids, cursor-resumable) and, for structural lifecycle events,
  through `state_store.append_event` (persisted to `events.json` for restart
  recovery). Never add a side channel for output. Readers resume by cursor; never
  return the *tail* of unseen events (see the comment in `EventBus.events_after`) —
  that silently drops the oldest unseen events.
- **Headroom optimizes model *input* only, and must stay optional and fail-open.**
  [headroom_service.py](../backend/agentflow/headroom_service.py) is off by default
  (`headroom.enabled`), gated by a bounded (~300 ms) cached TCP reachability probe,
  and `proxy_env()` returns `{}` when disabled or unreachable so the agent runs
  direct. Headroom must never be required for ordinary execution and must never
  delay a spawn or live output. Measured savings are reported as a
  `TokenEfficiencyReport`; unmeasured fields stay `null` and are never fabricated.
- **Deterministic contracts are versioned and validated.** Every contract in
  [contracts.py](../backend/agentflow/contracts.py) carries a `version` and a `kind`.
  Adding or altering one is a versioned change. `contracts.validate(kind, data)`
  never raises on bad input — it returns a structured `FailureRecord` for unknown
  kinds, unsupported versions, and schema violations. Readers reject unknown variants
  safely; no crash, no self-correction loop.
- **One markdown renderer.** [Markdown.tsx](../frontend/src/components/Markdown.tsx)
  is the only markdown renderer; it builds React elements and never uses
  `dangerouslySetInnerHTML` for agent text. Do not introduce a competing renderer or
  a second `parseSegments`.
- **Loopback-only bind.** The server binds `127.0.0.1` only. There is no auth by
  design; the security boundary is the loopback interface plus the origin allowlist
  ([origins.py](../backend/agentflow/origins.py) +
  `OriginGuardMiddleware` in [app.py](../backend/agentflow/app.py)).
- **No `shell=True`; explicit argv.** Subprocesses spawn via
  `asyncio.create_subprocess_exec(*argv, ...)` with `start_new_session=True`. Build
  `argv` as a list; never interpolate user/agent strings into a shell line.
- **Git uses `--` separators.** Git invocations that take a path place it after `--`
  (see [git_service.py](../backend/agentflow/git_service.py), e.g.
  `diff --cached -- <path>`, `add -- <path>`) so a path can never be parsed as a flag.
- **Secrets are redacted before persist or broadcast.** All event/log/ledger output
  passes through [redaction.py](../backend/agentflow/redaction.py). The event bus
  redacts `detail`, `textDelta`, and structured `data` at publish time as a
  defense-in-depth boundary. Live stream deltas are cut at a whitespace boundary
  (`_split_emittable`) so a secret is never split across a delta and emitted
  half-redacted. Never redact in the browser.

## 3. Authoritative contracts (the machine-readable truth)

- **Deterministic semantic layer:** [contracts.py](../backend/agentflow/contracts.py).
  The Pydantic models there (`TaskDirective`, `QueueDirective`, `RunDirective`,
  `DoneDirective`, `NeedsUserDirective`, `CommandSummary`, `TestSummary`,
  `FailureRecord`, `ApprovalRequest`, `TaskSummary`, `AgentHandoff`,
  `TokenEfficiencyReport`) are the structured meaning of controller and agent
  decisions. `CONTRACT_VERSION` and the `_REGISTRY` map are the source of truth for
  what `kind`s exist.
- **HTTP surface:** the live OpenAPI schema at `/docs` (and `/openapi.json`) on the
  running backend. Treat the running server, not prose, as the route reference.
- **SSE event shape:** the dict produced by `EventBus.publish`
  ([event_bus.py](../backend/agentflow/event_bus.py)) — `id`, `type`, `createdAt`/
  `time`, `workspacePath`, `provider`, `taskId`, `runId`, `queueItemId`, `step`,
  `sequence`, `channel`, `textDelta`, `redacted`, `truncated`, `detail`, `data`. On
  the frontend, network input is validated at the boundary by `coerceStreamEvent`
  ([lib/streamEvent.ts](../frontend/src/lib/streamEvent.ts)) before it reaches the
  store. Event `type`s and `stream_kind`s are assigned in
  [process_runner.py](../backend/agentflow/process_runner.py) (`run.output`,
  `run.stderr`, `chat.delta`, `controller.delta`, `command.started/finished`,
  `run.started/cancelled`, `run.heartbeat`, `chat.finished`).

## 4. Generated / build areas (do not hand-edit; gitignored)

These are produced by the build and are ignored by git (see
[.gitignore](../.gitignore)). Never edit them by hand or commit them.

- `frontend/dist/` — the Vite production bundle (`tsc && vite build`); the backend
  serves it on `:8787` in single-port mode.
- `/dist/` and `dist-app/` — packaging output (e.g. the macOS app-mode build).

Source of truth lives in `backend/agentflow/` and `frontend/src/`.

## 5. Commands that MUST pass before you are done

One command surface, identical locally and in CI:

```bash
make verify
```

`make verify` runs format-check, lint (`ruff` + `eslint`), typecheck (`mypy` +
`tsc --noEmit`), tests (`pytest --cov=agentflow` + `vitest run`), and the build. See
[ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md) for the per-task breakdown and
the [Makefile](../Makefile). Backend tests run hermetically (no reads/writes to the
real `~/.agentflow`; see [backend/tests/conftest.py](../backend/tests/conftest.py))
and deterministically (poll with a timeout, never `sleep`). Coverage must not drop
below the `fail_under` gate in `pyproject.toml`.

Useful subsets while iterating:

```bash
.venv/bin/python -m pytest backend/tests        # backend suite
npm --prefix frontend run test                  # vitest
make dev                                         # or scripts/dev.sh — local run
```

The pillar acceptance tests
([backend/tests/test_pillars.py](../backend/tests/test_pillars.py),
[test_headroom_service.py](../backend/tests/test_headroom_service.py),
[test_contracts.py](../backend/tests/test_contracts.py), and the frontend
`lib/*.test.ts`) exist to prove the invariants above. If you weaken a pillar you
will break them; that is intended.

## 6. Files to update for specific changes

Do not duplicate the table — it is maintained in one place:
[Documentation maintenance matrix](DEVELOPMENT.md#documentation-maintenance-matrix).
When you change a route/service, a contract, the event envelope, an env var, the
startup/build path, origins, the process runner, the auto-run policy, a frontend
page, or the tooling thresholds, review the docs that row lists in the *same* change.
The "how to make common changes" recipes are in
[DEVELOPMENT.md](DEVELOPMENT.md#how-to-make-common-changes) (add a route, service,
schema, page, component, workflow, test, config variable).

## 7. Security-sensitive areas (touch with extra care)

Review any change to these against [SECURITY.md](SECURITY.md):

- [process_runner.py](../backend/agentflow/process_runner.py) — subprocess spawn,
  incremental read, redaction-on-stream, cancellation, watchdog, bounded capture.
- [policy_service.py](../backend/agentflow/policy_service.py) — auto-run/approval
  allowlist; see [adr/0001-auto-run-policy-allowlist.md](adr/0001-auto-run-policy-allowlist.md).
- [workspace.py](../backend/agentflow/workspace.py) — workspace-containment checks
  for every agent/user-supplied filesystem path.
- [origins.py](../backend/agentflow/origins.py) — the CORS/CSRF/WebSocket origin
  allowlist that backs `OriginGuardMiddleware`.
- [redaction.py](../backend/agentflow/redaction.py) — the single secret-redaction
  boundary all output passes through.

## 8. Common mistakes (do not do these)

- **Adding a second markdown or command renderer.** There is exactly one of each;
  compose the shared primitives (`Markdown`, `TimelineCard`, `RawDetail`,
  `displayModel.ts`) instead of re-interpreting events per surface.
- **Making Headroom required.** It must stay off-by-default and fail-open; never let
  it gate or delay a spawn or live output.
- **Animating completed text.** Live reveal applies to genuine appends while a
  producer is active ([SmoothStreamingText.tsx](../frontend/src/components/SmoothStreamingText.tsx)
  snaps when inactive / reduced-motion). Do not run a typewriter animation over
  already-complete text, and do not wait for process exit / `communicate()` before
  showing the first chunk (Pillar 2).
- **Parsing controller decisions from prose.** Controller/agent decisions are
  validated records (`chat_directives.controller_directive_records` →
  `contracts.validate`), not regex guesses over free text on the read side.
- **Blocking the event loop.** The backend is async; long or blocking work belongs in
  the threadpool or a background task. Background tasks must be referenced so they are
  not GC'd mid-flight (see `ProcessRunner._spawn` / `_bg_tasks`). Every network/
  subprocess call has a timeout except intentionally long-lived runs, which instead
  have a cancellation path and a watchdog (`AGENT_RUN_TIMEOUT`).
- **Putting business logic in a route** instead of a service, or **`fetch`ing from a
  component** instead of going through [api.ts](../frontend/src/api.ts).
- **Unbounded buffers/retries** or **swallowing exceptions** without an annotated
  boundary (`# noqa: BLE001 — reason`).

## 9. Known misleading / legacy areas

These will trip you up if you trust the name over the code:

- **Four-way project naming.** The same product appears as: the full name
  **"Command Line Interface Traffic Controller"** (per [DESIGN.md](../DESIGN.md)),
  the compact UI name **"CLIT Controller IDE"**, the short forms **CLITC** /
  **CLIT Controller**, the Python package **`agentflow`** (entry
  `python -m agentflow`), and the repo root directory **AgentComposer**. They are all
  the same thing. Note also that [app.py](../backend/agentflow/app.py) sets the
  FastAPI `title` to "Command Line Interface **Terminal** Controller", which diverges
  from DESIGN.md's "**Traffic** Controller" full name — a known inconsistency, not two
  products.
- **`DESIGN.md`** at the repo root is the *visual* design language (radius scale,
  density, color, naming), not the system architecture. For architecture read
  [docs/ARCHITECTURE.md](ARCHITECTURE.md); for the product model read
  [docs/PILLARS.md](PILLARS.md).
- **Overlapping launcher scripts** in [scripts/](../scripts): `dev.sh` (local dev
  servers), `install.sh` (setup), `headroom.sh` (optional proxy on `:8799`),
  `app-mode.sh`, `app.sh`, `make-app.sh`, and `create-macos-app-mode.sh` (macOS
  app-mode packaging — several overlapping variants). The two you usually want are
  `dev.sh` to run and `install.sh` to set up; confirm which packaging script is
  current with [OPERATIONS.md](OPERATIONS.md) rather than guessing from the filename.
- **`time` vs `createdAt`** on events: `time` is a back-compat alias for `createdAt`;
  do not introduce code that depends on only one.

## 10. Definition of done

A change is done when:

- `make verify` passes locally and CI is green on the PR.
- It is the smallest coherent unit; repo-wide formatting is not mixed with behavior
  (formatting lands in its own commit).
- New behavior has a test; every fixed bug has a regression test; the suite stays
  hermetic and deterministic and coverage does not regress.
- No new frontend `any`; no unexplained `# type: ignore` / `Any` / `noqa` in the
  backend (inline reason required).
- The architectural invariants in §2 are intact (canonical stream as truth, Headroom
  optional/fail-open, contracts versioned/validated, one markdown renderer,
  loopback-only, no `shell=True`, git `--` separators, redaction before persist/
  broadcast).
- Docs are updated per the
  [maintenance matrix](DEVELOPMENT.md#documentation-maintenance-matrix).

## 11. Required final reporting format

When you finish, report — concisely, no model hype — in this shape:

1. **What changed** — the files touched and, for each, the one-line reason.
2. **Why** — the goal, tied to the pillar(s) it serves or the bug it fixes.
3. **Invariants checked** — confirm the §2 invariants you could have affected still
   hold (e.g. "Headroom still fail-open; redaction still at the bus; no new
   renderer").
4. **Verification** — the exact commands you ran and their result (`make verify`
   pass/fail, any subset suites, manual checks).
5. **Tests** — the test(s) added or updated, and which pillar/regression they cover.
6. **Docs** — the maintenance-matrix rows you reviewed and the docs you updated.
7. **Follow-ups / limitations** — anything left partial, with a pointer to
   [LIMITATIONS.md](LIMITATIONS.md) / [ROADMAP.md](ROADMAP.md) if tracked there.

Use repo-relative links and copyable commands. Classify any feature you describe
honestly (Implemented / Partially implemented / Mocked / Experimental / Planned /
Deprecated). Inspect the actual code before asserting behavior; never invent
commands, files, ports, env vars, or features.
