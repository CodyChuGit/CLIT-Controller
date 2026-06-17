# Development

How to work in **CLIT Controller IDE** (AgentComposer): set up, make a change,
verify it, and hand off cleanly. This is the contributor playbook. The *rules*
those changes must obey live in [ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md)
— this page does not repeat them, it tells you how to satisfy them.

For the bigger picture, read [PILLARS.md](PILLARS.md) (what the product is and the
five pillars), [ARCHITECTURE.md](ARCHITECTURE.md) (how it fits together), and
[OPERATIONS.md](OPERATIONS.md) (runtime, ports, state).

## First-time setup

```bash
make setup        # ./scripts/install.sh: creates .venv (Python 3.11+), installs
                  # backend ".[dev]" + frontend npm deps
```

`make setup` finds a Python ≥ 3.11 (the macOS system `python3` is 3.9 and will not
work), creates `.venv`, installs the backend editable with dev extras, and runs
`npm install` in `frontend/`. If `npm install` hits a `~/.npm` permissions error it
retries with an isolated cache automatically (see [install.sh](../scripts/install.sh)).

## Branch workflow

- `main` is the default and only long-lived branch; CI runs on every push to `main`
  and on every pull request (see [ci.yml](../.github/workflows/ci.yml)).
- Branch off `main`, keep the change small and coherent, run `make verify`, open a PR.
- Do not combine repo-wide reformatting with behavior changes — formatting lands in
  its own commit (see [ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md) calibration notes).
- Every fixed defect gets a regression test in the same PR.

## Dev servers + hot reload

```bash
make dev          # ./scripts/dev.sh
```

This runs two processes ([dev.sh](../scripts/dev.sh)):

- **Backend** `python -m agentflow` on `http://localhost:8787` — FastAPI via uvicorn,
  serves the API and (if `frontend/dist` exists) the built frontend.
- **Frontend** Vite dev server on `http://localhost:5180` — React + HMR, proxies
  `/api` and the WebSocket endpoints to `:8787` (see [vite.config.ts](../frontend/vite.config.ts)).

Develop against **`:5180`** for hot reload. `dev.sh` frees both ports before
starting (so duplicate backends / vite servers can't pile up) and, on exit, stops
the backend gracefully so it reaps its PTY terminal children (claude/codex/agy).

Backend has no auto-reload wired in — restart `make dev` after backend changes.
Single-port production mode (`make build`, then the backend serves `dist` on
`:8787`) is for verifying the shipped artifact, not day-to-day work.

## Quality commands

Identical locally and in CI. Run individually while iterating; run `make verify`
before pushing.

| Stage | Backend | Frontend | Combined |
|-------|---------|----------|----------|
| format (write) | `ruff format backend` | `npm --prefix frontend run format` (prettier) | `make format` |
| format (check) | `ruff format --check backend` | `npm --prefix frontend run format:check` | `make format-check` |
| lint | `ruff check backend` | `npm --prefix frontend run lint` (eslint) | `make lint` |
| typecheck | `mypy` | `npm --prefix frontend run typecheck` (`tsc --noEmit`) | `make typecheck` |
| test | `.venv/bin/python -m pytest backend/tests --cov=agentflow` | `npm --prefix frontend run test` (vitest) | `make test` |
| build | (import smoke via tests) | `npm --prefix frontend run build` (`tsc && vite build`) | `make build` |

Config lives in [pyproject.toml](../pyproject.toml) (ruff: line-length 120, rules
`E,W,F,I,B`; mypy: `files = backend/agentflow`, `no_implicit_optional`,
`check_untyped_defs`; coverage `fail_under = 55`) and [frontend/package.json](../frontend/package.json).
Coverage below the gate fails CI, so it cannot silently regress.

## How to make common changes

### Add a backend route

1. Add the endpoint to the relevant module in [backend/agentflow/api/](../backend/agentflow/api/)
   (e.g. [routes_tasks.py](../backend/agentflow/api/routes_tasks.py)). Each module
   exposes a `router = APIRouter()`. For workspace-scoped data, depend on
   `require_workspace()` from `routes_projects`.
2. For a brand-new area, create `routes_<area>.py`, then register it in
   [app.py](../backend/agentflow/app.py) with `app.include_router(... prefix="/api/<area>", tags=["<area>"])`.
3. Keep handlers thin — they validate input and delegate to a service. No business
   logic in the route.

### Add a backend service

Add a module at `backend/agentflow/<name>_service.py` (peer of
[task_service.py](../backend/agentflow/task_service.py),
[queue_service.py](../backend/agentflow/queue_service.py)). Services own logic and
state I/O. Use [state_store.py](../backend/agentflow/state_store.py) /
[paths.py](../backend/agentflow/paths.py) for the JSON ledger and atomic writes,
[process_runner.py](../backend/agentflow/process_runner.py) to spawn subprocesses
(explicit `argv`, never `shell=True`), and emit canonical events via
[event_bus.py](../backend/agentflow/event_bus.py) rather than inventing a side
channel. Run anything that touches logs/events/payloads through
[redaction.py](../backend/agentflow/redaction.py).

### Add a request/response schema

Request bodies are Pydantic models in [models.py](../backend/agentflow/models.py)
(e.g. `TaskCreateRequest`). **Semantic output contracts** — controller decisions,
command/test results, summaries, hand-offs — go in
[contracts.py](../backend/agentflow/contracts.py): every contract carries a
`version` and a `kind` discriminator, and is parsed via `validate()` which fails
*safely* on unknown/invalid payloads. Adding or altering a contract is a **versioned**
change; readers must reject unknown variants safely, not crash.

### Add a frontend page

1. Create `frontend/src/pages/<Name>Page.tsx`.
2. Wire it into [App.tsx](../frontend/src/App.tsx): import it, add its id to the
   `PageId` list / `PAGE_IDS`, and add the `{page === "<id>" && <NamePage />}` branch.
   Add the nav entry in [ActivityBar.tsx](../frontend/src/components/ActivityBar.tsx).
3. Every route-level view must be wrapped so a render failure can't white-screen the
   app — see [ErrorBoundary.tsx](../frontend/src/components/ErrorBoundary.tsx).

### Add a frontend component

Add it under `frontend/src/components/`. Reuse the shared primitives in
[ui.tsx](../frontend/src/components/ui.tsx) and [icons.tsx](../frontend/src/components/icons.tsx).
Render Markdown only through the single renderer [Markdown.tsx](../frontend/src/components/Markdown.tsx).
Select UI by contract `kind`, not by sniffing text.

### Add an API-backed workflow

All network access is centralized in [frontend/src/api.ts](../frontend/src/api.ts)
(the `request<T>` helper prefixes `/api`). Add a typed function there and its types
in [types.ts](../frontend/src/types.ts) — components never `fetch` directly.
Responses cross the trust boundary, so validate or defensively handle them; never
assume well-formed. Give the workflow intentional loading / empty / error / retry
states. For live agent/event output, consume the canonical stream via
[stream.tsx](../frontend/src/stream.tsx) and [lib/streamEvent.ts](../frontend/src/lib/streamEvent.ts).

### Add a test

- **Backend:** add `backend/tests/test_<area>.py` (pytest). The suite is **hermetic** —
  the autouse fixture in [conftest.py](../backend/tests/conftest.py) redirects
  `~/.agentflow` and `$HOME` to a temp dir, so never touch real global state.
  Keep tests deterministic: poll with a timeout, no `sleep`-based timing.
- **Frontend:** add `*.test.ts(x)` next to the unit under test (vitest + Testing
  Library), e.g. [Markdown.test.tsx](../frontend/src/components/Markdown.test.tsx).

### Add a config variable

Runtime config is **file-based**, not env-based: global `~/.agentflow/config.json`
and per-workspace `<workspace>/.agentflow/config.json` via
[config.py](../backend/agentflow/config.py). The only sanctioned env knobs are
`AGENTFLOW_PORT` and `SHELL`; if you add another, document it in
[.env.example](../.env.example) and [OPERATIONS.md](OPERATIONS.md). No secrets in
the repo. Pin new deps (`pyproject.toml` + `requirements.lock`, or `package.json` +
`package-lock.json`).

## Pre-push expectations

```bash
make verify       # format-check + lint + typecheck + test + build — mirrors CI exactly
```

CI ([ci.yml](../.github/workflows/ci.yml)) runs the same backend (ruff · mypy ·
pytest+cov) and frontend (eslint · prettier · tsc · vitest · build) steps on
Python 3.11 / Node 20. If `make verify` is green locally, CI will be too.

## Definition of done

- `make verify` passes locally (and CI is green on the PR).
- The change is the smallest coherent unit; formatting is not mixed with behavior.
- New behavior is covered by a test; every fixed bug has a regression test.
- No new `any` (frontend) and no unexplained `# type: ignore` / `Any` / `noqa`
  (backend) — inline reason required.
- Security invariants intact: loopback-only bind, no `shell=True`, every
  agent/user-supplied path is workspace-contained, output is redacted, buffers are
  bounded. See [SECURITY.md](SECURITY.md) and [ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md).
- Docs updated per the matrix below.

## Change checklist

1. Branch off `main`.
2. Make the change; add/extend a service or contract rather than thickening a route.
3. Add or update tests (hermetic, deterministic).
4. `make format && make verify`.
5. Update docs per the matrix.
6. Commit (formatting separate from behavior), push, open a PR.

## Documentation maintenance matrix

When you change one of these, review the listed docs in the same PR.

| Change type | Docs to review |
|-------------|----------------|
| New/changed API route or service | [ARCHITECTURE.md](ARCHITECTURE.md), this page |
| New/changed output contract (`contracts.py`) | [PILLARS.md](PILLARS.md) (Pillar 5), [ARCHITECTURE.md](ARCHITECTURE.md) |
| Event envelope / `event_bus` / `state_store` change | [ARCHITECTURE.md](ARCHITECTURE.md), [PILLARS.md](PILLARS.md) |
| New env var or config file field | [.env.example](../.env.example), [OPERATIONS.md](OPERATIONS.md) |
| Port / startup / build / runtime change | [OPERATIONS.md](OPERATIONS.md), this page (dev servers) |
| Origin / CORS / WS allowlist (`origins.py`) | [SECURITY.md](SECURITY.md) |
| Subprocess / PTY / process_runner change | [SECURITY.md](SECURITY.md), [ARCHITECTURE.md](ARCHITECTURE.md) |
| Auto-run / approval policy (`policy_service.py`) | [adr/0001-auto-run-policy-allowlist.md](adr/0001-auto-run-policy-allowlist.md), [SECURITY.md](SECURITY.md) |
| New frontend page / nav entry | [ARCHITECTURE.md](ARCHITECTURE.md), this page |
| Lint/type/test tooling or thresholds | [ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md), this page |
| A standard/invariant itself changes | [ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md) |

## AI agent handoff

If you are an AI agent picking up work here, start with this orientation.

**Read first (in order):**
1. [PILLARS.md](PILLARS.md) — the product and its five pillars; what "good" means.
2. [ARCHITECTURE.md](ARCHITECTURE.md) — how backend, frontend, and the event stream fit.
3. [contracts.py](../backend/agentflow/contracts.py) — the versioned semantic layer the UI selects on.
4. [event_bus.py](../backend/agentflow/event_bus.py) — the canonical event stream.

**Architectural invariants (do not violate):**
- The canonical event stream (`event_bus` / `state_store` ledger) is the single
  source of truth — never add a side channel for output.
- One markdown renderer ([Markdown.tsx](../frontend/src/components/Markdown.tsx)); do not introduce a second.
- Contracts are **versioned**; adding/altering one is a versioned change and readers reject unknown variants safely.
- **Loopback-only**: the server binds `127.0.0.1`; there is no auth by design.
- **No `shell=True`** — subprocesses spawn with explicit `argv` lists.

**Must pass before done:** `make verify`.

**Security-sensitive areas (touch with extra care, review against [SECURITY.md](SECURITY.md)):**
[process_runner.py](../backend/agentflow/process_runner.py),
[policy_service.py](../backend/agentflow/policy_service.py),
[workspace.py](../backend/agentflow/workspace.py),
[origins.py](../backend/agentflow/origins.py).

**Common mistakes to avoid:**
- Putting business logic in a route instead of a service.
- `fetch` from a component instead of going through [api.ts](../frontend/src/api.ts).
- Parsing agent text with regex instead of validating a contract by `kind`.
- Writing config to a new env var instead of the file-based config.
- Tests that touch the real `~/.agentflow` or use `sleep` instead of polling.
- Unbounded buffers/retries, or swallowing exceptions without an annotated boundary.
