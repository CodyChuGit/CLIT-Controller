# Testing

How CLIT Controller IDE / AgentComposer is tested, what kinds of tests exist,
and the exact commands to run them. The test suites are not incidental: the
product pillars are encoded as acceptance tests, so the suite is the executable
statement of what the product must do (see [PILLARS.md](PILLARS.md)).

The verification pipeline is identical locally and in CI — both run `make verify`.
For the broader engineering policy (when a test is required, the coverage gate
philosophy), see [ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md).

---

## Frameworks

| Side | Runner | Support libraries | Environment |
| --- | --- | --- | --- |
| Backend | [pytest](https://docs.pytest.org) `>=8.0` | `pytest-cov` (coverage), `httpx` (Starlette `TestClient`) | Python 3.11 venv at `.venv` |
| Frontend | [vitest](https://vitest.dev) `^2.1` | `@testing-library/react` (RTL), `@testing-library/jest-dom`, `@testing-library/user-event` | `jsdom` |

Backend config lives in [pyproject.toml](../pyproject.toml) under
`[tool.pytest.ini_options]`, `[tool.coverage.run]`, and `[tool.coverage.report]`.
Frontend config lives in the `test` block of
[frontend/vite.config.ts](../frontend/vite.config.ts) (it uses `vitest/config`,
so one file configures both the dev server and the test runner).

Static analysis runs alongside the tests as part of verification: `ruff` (lint) +
`mypy` (types) for the backend, `eslint` + `tsc --noEmit` for the frontend.

---

## Directory structure

```text
backend/tests/                 # pytest suite — flat directory, one file per concern
  conftest.py                  # hermetic autouse fixture (isolates ~/.agentflow)
  test_pillars.py              # cross-cutting pillar acceptance tests
  test_headroom_service.py     # Pillar 1
  test_contracts.py            # Pillar 5
  test_*.py                    # service / route / streaming / cancel / security units
frontend/src/
  test/setup.ts                # vitest global setup (jest-dom matchers)
  lib/*.test.ts                # pure-helper unit tests (ansi, streamEvent, taskFormat)
  hooks/*.test.ts              # hook-helper tests (useAutoScroll)
  components/*.test.tsx         # component tests (Markdown, ErrorBoundary)
```

Backend tests are configured via `testpaths = ["backend/tests"]`, so `pytest`
discovers them from the repo root. Frontend tests are colocated next to the code
they cover (`*.test.ts` / `*.test.tsx`).

Current size: **165 backend test functions**, **26 frontend test cases**.

---

## What kinds of tests exist

### Backend

- **Service / unit** — exercise a single service module against throwaway state:
  state store, queue, routing, usage, recovery, policy, git, transitions, redaction.
- **Route via `TestClient`** — Starlette's in-process `TestClient` (backed by
  `httpx`) drives the real ASGI app from `create_app()` without binding a socket.
  Used for HTTP routes and the cross-origin guard
  ([test_csrf.py](../backend/tests/test_csrf.py)) — it asserts that mutating
  `POST`s with a foreign `Origin`/`Referer` get `403`, app-origin and
  Origin-less requests pass, and `GET` is never origin-guarded.
- **WebSocket** — `TestClient.websocket_connect` pins the security-critical
  live-terminal route ([test_routes_terminals.py](../backend/tests/test_routes_terminals.py)):
  the CSWSH `Origin` allow-list (foreign origin closes with `4403`), the
  unknown-provider close code (`4404`), and workspace gating. These exercise only
  the gating paths and never spawn a real shell.
- **Streaming** — [test_streaming.py](../backend/tests/test_streaming.py) drives a
  real subprocess through `ProcessRunner` and asserts ordered, redacted, resumable
  deltas land on the event bus, plus the command lifecycle events.
- **Cancel / reaping** — [test_process_cancel.py](../backend/tests/test_process_cancel.py)
  pins the `SIGTERM`→`SIGKILL` escalation, timeout reaping, the runtime watchdog,
  and start-failure status, verifying that hung process groups are actually
  reaped (no leaked PIDs).

### Frontend

- **Pure-helper** — fast, DOM-free unit tests of library functions:
  `lib/ansi.test.ts` (`stripAnsi`/`hasAnsi`), `lib/streamEvent.test.ts`
  (`coerceStreamEvent` network-input validation), `lib/taskFormat.test.ts`
  (`formatDuration`/`shortPath`/`describeCommand`), `hooks/useAutoScroll.test.ts`
  (`isNearBottom`).
- **Component** — RTL renders into `jsdom`: `components/Markdown.test.tsx` proves
  hostile agent output is rendered as inert text, never live DOM (no `<script>`/`<img>`
  injection); `components/ErrorBoundary.test.tsx` proves the boundary renders a
  recoverable fallback when a child throws.

---

## The hermetic fixture

The whole backend suite must never read or write the developer's real global
state under `~/.agentflow`. [backend/tests/conftest.py](../backend/tests/conftest.py)
defines an **autouse** fixture, `isolated_global_state`, that runs for every test:

- It creates a uniquely-named temp `fakehome` (never under, or a string prefix of,
  the test's `tmp_path` workspace — otherwise `~`-relative paths could resolve
  "inside" the workspace and break path-confinement assertions).
- It monkeypatches `paths.global_config_dir()` to point at `<fakehome>/.agentflow`
  **and** sets `$HOME` to `<fakehome>`, so both the explicit accessor and any code
  reaching for `Path.home()` directly stay inside the sandbox.

Per-workspace state already lives under each test's `tmp_path`. The net effect:
selecting a workspace, recording usage, sweeping terminal sessions, etc. all
operate on throwaway state, and the suite is safe to run on a developer machine
with a real configured workspace.

The frontend equivalent is [frontend/src/test/setup.ts](../frontend/src/test/setup.ts),
the `setupFiles` entry that loads `@testing-library/jest-dom/vitest` so DOM
matchers (`toBeInTheDocument`, `toHaveTextContent`, …) are available globally.

---

## Coverage gate

Coverage is measured with `pytest-cov` and enforced through
[pyproject.toml](../pyproject.toml):

- `[tool.coverage.run]` — `source = ["agentflow"]`, `branch = true` (branch
  coverage, not just line).
- `[tool.coverage.report]` — `show_missing = true`, **`fail_under = 55`**.

The `fail_under` is an honest baseline the suite currently clears (actual is
~60%); CI fails below it so coverage cannot silently regress. Raise the gate as
coverage grows — do not lower it to make a change pass.

There is no enforced coverage gate on the frontend suite.

---

## The pillar test suite

The five product pillars ([PILLARS.md](PILLARS.md)) are the success metrics, and
dedicated suites prove them rather than testing implementation trivia:

- **Pillar 1 — token saving / output speed:**
  [test_headroom_service.py](../backend/tests/test_headroom_service.py). Asserts
  Headroom is off by default and returns no env, fails open when enabled but
  unreachable, routes `claude`→`ANTHROPIC_BASE_URL` and `codex`→`OPENAI_BASE_URL`
  (and leaves unsupported providers alone), and that the reachability probe is
  bounded (`_PROBE_TIMEOUT <= 0.5`s) so a spawn is never delayed. End-to-end, it
  spawns through `ProcessRunner` to confirm the base URL is injected only when
  enabled+reachable (`headroom_applied` reflects this).
- **Pillar 5 — deterministic output contracts:**
  [test_contracts.py](../backend/tests/test_contracts.py). Every registered
  contract is versioned and kinded; valid payloads round-trip; unknown kinds,
  unsupported versions, and invalid schemas all return a structured `FailureRecord`
  instead of raising; controller directives parse into kinded records that each
  validate. The frontend mirror is `lib/streamEvent.test.ts` (network frames are
  validated/normalized before they enter the store).
- **Pillars 2 & 3 (backend half) —** [test_pillars.py](../backend/tests/test_pillars.py).
  Pillar 2 (true live output) is proven deterministically: a child prints a chunk
  then stays alive ~1s, and a delta carrying that chunk must be observable on the
  event bus *while the run status is still `running`* — not only after exit.
  Pillar 3 (secrets never reach the stream) is proven by printing a token from a
  child and asserting the streamed deltas contain `[REDACTED]` and never the raw
  secret.
- **Pillars 3 & 4 (frontend half) —** `lib/ansi.test.ts` (readable presentation —
  ANSI stripped, text kept), `components/Markdown.test.tsx` (untrusted output is
  inert), `hooks/useAutoScroll.test.ts` (Pillar 4 consistent auto-scroll).

A change that improves one pillar while materially weakening another needs
explicit justification, and the pillar test that protects the weakened property
must still pass.

---

## Commands

All commands run from the repo root. The backend uses the project venv at `.venv`
(the system `python3` is 3.9; the venv is 3.11).

### Run everything

```bash
make test          # backend + frontend
make verify        # format-check + lint + typecheck + test + build (mirrors CI)
```

### Backend

```bash
# Whole backend suite
.venv/bin/python -m pytest backend/tests

# With coverage (what `make test-backend` runs)
.venv/bin/python -m pytest backend/tests --cov=agentflow

# A single file
.venv/bin/python -m pytest backend/tests/test_pillars.py

# A single test by name (substring match)
.venv/bin/python -m pytest backend/tests -k test_pillar3_secrets_never_reach_the_live_stream
```

### Frontend

```bash
# Whole frontend suite (one-shot)
npm --prefix frontend run test

# Watch mode
npm --prefix frontend run test:watch

# A single file
npm --prefix frontend run test -- src/lib/ansi.test.ts
```

### Static analysis

```bash
make lint          # ruff check backend  +  eslint
make typecheck     # mypy  +  tsc --noEmit
```

---

## What to test per change type

| Change | Required test |
| --- | --- |
| Bug fix | A regression test that fails before the fix and passes after. |
| New service / module function | Unit test against throwaway state (rely on the hermetic fixture; use `tmp_path` for the workspace). |
| New / changed HTTP route | Route test via `TestClient` against `create_app()`; cover the failure/guard paths, not just the happy path. |
| New WebSocket behavior | A gating/handshake test like [test_routes_terminals.py](../backend/tests/test_routes_terminals.py) (avoid spawning real shells). |
| Anything touching live output, redaction, or contracts | Extend the relevant pillar suite — these properties are user-facing guarantees. |
| Process lifecycle (spawn/cancel/timeout) | A reaping test that asserts no PID leaks ([test_process_cancel.py](../backend/tests/test_process_cancel.py)). |
| Frontend helper | Pure-function test in `lib/` or `hooks/`. |
| Frontend component rendering untrusted output | RTL component test asserting inert/safe rendering. |

Keep coverage at or above the `fail_under` gate. Every fixed defect gets a
regression test (see [ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md)).

---

## Known gaps

- **No HTTP-level integration over a real bound server.** All route and WebSocket
  tests use Starlette's in-process `TestClient`; nothing exercises the app over a
  real socket on `127.0.0.1:8787`.
- **No browser end-to-end tests.** There is no Playwright (or equivalent) suite;
  frontend coverage stops at pure helpers and RTL component tests in `jsdom`.
- **No enforced frontend coverage gate.**

These and other tracked shortfalls live in [LIMITATIONS.md](LIMITATIONS.md).
