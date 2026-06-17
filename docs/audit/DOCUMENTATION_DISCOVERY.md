# Documentation Discovery — CLIT Controller IDE (AgentComposer)

Repository discovery pass for the documentation effort. Everything below is drawn
from inspecting the actual code, configuration, and existing docs in this repo (see
[Files used as evidence](#files-used-as-evidence)). It is descriptive, not aspirational:
features are classified honestly and conflicts between docs and code are called out.

## 1. Repository summary

CLIT Controller IDE (package `agentflow`, repo directory `AgentComposer`) is a
**local-first, single-user, macOS-oriented developer cockpit** that orchestrates CLI
coding agents (`codex`, `claude`, `agy`/antigravity) as subprocesses, runs PTY terminals
over WebSockets, manages a git workspace, and streams agent output live (SSE + polling).

- It binds **loopback only** (`127.0.0.1:8787`, env `AGENTFLOW_PORT`) and has **no
  authentication by design** — see [SECURITY.md](../SECURITY.md). Browser-origin safety
  is enforced by an allowlist shared across CORS, CSRF, and the WebSocket check
  ([origins.py](../../backend/agentflow/origins.py), `OriginGuardMiddleware` in
  [app.py](../../backend/agentflow/app.py)).
- There is **no database**: all state is plaintext JSON with atomic writes, a
  cursor-resumable event ledger, and startup recovery — global `~/.agentflow/` plus
  per-workspace `<workspace>/.agentflow/` (see [state_store.py](../../backend/agentflow/state_store.py),
  [ARCHITECTURE.md](../ARCHITECTURE.md)).
- The product is structured around **five pillars** ([PILLARS.md](../PILLARS.md)), with
  "Live Output Everywhere" as the defining experience.

## 2. Detected tech stack

| Layer | Technology | Evidence |
|---|---|---|
| Backend framework | FastAPI `>=0.110,<1` on Uvicorn `[standard]` | [pyproject.toml](../../pyproject.toml) |
| Backend validation | Pydantic v2 (`>=2.5,<3`) | [pyproject.toml](../../pyproject.toml), [contracts.py](../../backend/agentflow/contracts.py) |
| Backend runtime | Python `>=3.11` (venv at `.venv`; system `python3` is 3.9) | [pyproject.toml](../../pyproject.toml), [Makefile](../../Makefile) |
| Frontend framework | React 18.3 + Vite 5.4 + TypeScript 5.5 | [frontend/package.json](../../frontend/package.json) |
| Styling | Tailwind CSS 3.4, PostCSS, Autoprefixer | [frontend/package.json](../../frontend/package.json) |
| Terminal / syntax | xterm `@xterm/xterm` 6 + `addon-fit`; Prism.js 1.30 | [frontend/package.json](../../frontend/package.json) |
| Backend QA | ruff (lint+format), mypy, pytest, pytest-cov, pip-audit | [pyproject.toml](../../pyproject.toml) |
| Frontend QA | eslint 9, prettier 3, tsc, vitest 2 (+ Testing Library, jsdom) | [frontend/package.json](../../frontend/package.json) |
| Dependency pinning | abstract ranges in `pyproject.toml`; exact pins in [requirements.lock](../../requirements.lock); npm `package-lock.json` | [pyproject.toml](../../pyproject.toml) |

## 3. Detected apps / packages

This is a **single repository with two co-located deliverables** and a set of shell
scripts; there is no monorepo workspace tool.

- **`agentflow`** — the backend Python package. Declared in `[tool.setuptools.packages.find]`
  (`where = ["backend"]`, `include = ["agentflow*"]`), distribution name
  `clit-controller-ide` v0.1.0 ([pyproject.toml](../../pyproject.toml)). 30 modules under
  [backend/agentflow/](../../backend/agentflow/) plus 10 routers under
  [backend/agentflow/api/](../../backend/agentflow/api/).
- **`clit-controller-ide-frontend`** — the React app, npm package v0.1.0 under
  [frontend/](../../frontend/). Not published; `"private": true`.
- **Backend test suite** — 31 `test_*.py` files under [backend/tests/](../../backend/tests/).
- **Frontend tests** — colocated `*.test.ts(x)` (e.g. `lib/ansi.test.ts`,
  `lib/streamEvent.test.ts`, `hooks/useAutoScroll.test.ts`,
  `components/ErrorBoundary.test.tsx`, `components/Markdown.test.tsx`, `lib/taskFormat.test.ts`).
- **Scripts** — [scripts/](../../scripts/): `install.sh`, `dev.sh`, `headroom.sh`,
  `app-mode.sh`, `app.sh`, `make-app.sh`, `create-macos-app-mode.sh`.

## 4. Runtime entry points

- **Backend process**: `python -m agentflow` →
  [backend/agentflow/__main__.py](../../backend/agentflow/__main__.py), which runs
  `uvicorn.run("agentflow.app:app", host="127.0.0.1", port=AGENTFLOW_PORT or 8787)`.
- **FastAPI app object**: `app = create_app()` in
  [backend/agentflow/app.py](../../backend/agentflow/app.py). Mounts 10 routers under
  `/api/*`, a `/api/health` endpoint, and — when `frontend/dist/index.html` exists —
  serves the built SPA on the same port (single-port mode) with a path-traversal-guarded
  catch-all. A `_lifespan` context does startup recovery, orphaned-PTY sweep, and runs the
  queue dispatcher loop.
- **Frontend dev server**: `vite` on port **5180**, proxying `/api` (with `ws:true`) to
  `127.0.0.1:8787` ([frontend/vite.config.ts](../../frontend/vite.config.ts)). Frontend
  root component `App.tsx` → `main.tsx` ([frontend/src/](../../frontend/src/)).
- **Production build**: `tsc && vite build` → `frontend/dist`, served by the backend on
  `:8787` (single-port mode).
- **Optional Headroom proxy**: `scripts/headroom.sh` starts `headroom proxy` on `:8799`
  (Pillar 1); the backend routes `claude`/`codex` children through it when enabled and
  reachable ([headroom_service.py](../../backend/agentflow/headroom_service.py)).

## 5. Existing-documentation inventory

Root-level docs:

| File | One-line purpose |
|---|---|
| [README.md](../../README.md) | Product pitch, install, requirements, dev command surface, roadmap. |
| [DESIGN.md](../../DESIGN.md) | Design language: tokens, layout primitives, component rules, Agent Dock / Tasks specs. |
| [NEXT_STEPS.md](../../NEXT_STEPS.md) | Forward-looking phase list (polish → productize → extend). |
| [.env.example](../../.env.example) | The two real env knobs (`AGENTFLOW_PORT`, `SHELL`) and the "no API keys here" note. |

`docs/`:

| File | One-line purpose |
|---|---|
| [docs/ARCHITECTURE.md](../ARCHITECTURE.md) | What the code actually does: transport, services, state, recovery; calls out divergence from design notes. |
| [docs/OPERATIONS.md](../OPERATIONS.md) | Runtime model, install/run, ports, state layout, lockfile, troubleshooting. |
| [docs/SECURITY.md](../SECURITY.md) | Security posture: loopback-only, no-auth, command execution, origin guard, redaction. |
| [docs/ENGINEERING_STANDARDS.md](../ENGINEERING_STANDARDS.md) | The repo's enforced rules (lint/format/type/test gates, style calibration). |
| [docs/PILLARS.md](../PILLARS.md) | Authoritative statement of the 5 product pillars + interaction model. |
| [docs/live-output-everywhere.md](../live-output-everywhere.md) | Design note: making assistant work immediate/readable/continuous across the app. |
| [docs/local-voice-io.md](../local-voice-io.md) | Design note: optional local STT (MLX Parakeet) / TTS, review-first. |
| [docs/phase-1-5-product-workbench.md](../phase-1-5-product-workbench.md) | Design note: Phase 1.5 workbench (readable task output, reference DB, overflow scheduling). |
| [docs/streaming-renderer-decision.md](../streaming-renderer-decision.md) | Design note: smooth CLI-like type-out renderer on top of the shared event stream. |
| [docs/task-controller-io-surface.md](../task-controller-io-surface.md) | Design note: one I/O language across the controller tab and Tasks page. |
| [docs/text-streaming-across-the-board.md](../text-streaming-across-the-board.md) | Design note: streaming as a shared product/backend contract everywhere. |
| [docs/vscode-style-agent-dock.md](../vscode-style-agent-dock.md) | Design note: native VS Code-style Agent Dock + Tasks tab (no real VS Code dependency). |
| [docs/pwa-chrome-app-mode.md](../pwa-chrome-app-mode.md) | Design note: app-like Chrome window via PWA, no Electron/Tauri/Chrome Apps. |
| [docs/audit/INITIAL_AUDIT.md](INITIAL_AUDIT.md) | Baseline multi-agent audit with adversarially verified P1/P2/P3 findings. |
| [docs/audit/FINAL_REPORT.md](FINAL_REPORT.md) | Production-hardening final report; companion to the initial audit. |
| [docs/adr/0001-auto-run-policy-allowlist.md](../adr/0001-auto-run-policy-allowlist.md) | ADR: targeted auto-run command hardening rather than full allowlist inversion. |
| [docs/orchestrator-backend/README.md](../orchestrator-backend/README.md) | Controller backend strategy index (target capability set). |
| [docs/orchestrator-backend/01-target-capability.md](../orchestrator-backend/01-target-capability.md) | Target controller capability definition. |
| [docs/orchestrator-backend/02-architecture-contracts.md](../orchestrator-backend/02-architecture-contracts.md) | Target architecture + contracts for the controller backend. |
| [docs/orchestrator-backend/03-implementation-roadmap.md](../orchestrator-backend/03-implementation-roadmap.md) | Implementation roadmap toward the target controller backend. |
| [docs/orchestrator-backend/04-verification-and-operations.md](../orchestrator-backend/04-verification-and-operations.md) | Verification + operations plan for the target backend. |

Non-doc assets under `docs/`: `assets/` (README screenshots), `icon-options/`, `.DS_Store`.

## 6. Documentation conflicts / staleness found

1. **Product-name inconsistency (highest impact).** The product expands to two different
   names across the repo:
   - "Command Line Interface **Terminal** Controller" — in [app.py](../../backend/agentflow/app.py)
     (`FastAPI(title=...)`), [__main__.py](../../backend/agentflow/__main__.py),
     [__init__.py](../../backend/agentflow/__init__.py), `provider_probe.py`,
     `prompt_templates.py`, `paths.py`, `process_runner.py`, `ActivityBar.tsx`,
     and [ARCHITECTURE.md](../ARCHITECTURE.md)/[OPERATIONS.md](../OPERATIONS.md).
   - "Command Line Interface **Traffic** Controller" — in [README.md](../../README.md),
     [DESIGN.md](../../DESIGN.md) (naming section + first-mention rule), and several design
     notes (`text-streaming-across-the-board.md`, `vscode-style-agent-dock.md`,
     `streaming-renderer-decision.md`, `pwa-chrome-app-mode.md`,
     `ARCHITECTURE.md` references the divergence, `orchestrator-backend/*`).
     Note `ARCHITECTURE.md` actually contains **both** spellings. This must be resolved to a
     single canonical expansion before the documentation pass treats either as authoritative.

2. **DESIGN.md describes target/aspirational UI that exceeds shipped code.** DESIGN.md
   specifies a "UI/UX Reference Tab", "Local Voice I/O" controls, and a full "Agent Dock"
   provider-tab/terminal-drawer language. The shipped frontend has `pages/` for projects,
   agents, tasks, terminals, preview, usage, logs, settings ([App.tsx](../../frontend/src/App.tsx))
   and a `ChatPanel`/`tasks/` surface, but there is **no reference-library page** and **no
   voice components** in `frontend/src/`. These should be classified as Planned/Partially
   implemented, not described as present.

3. **README install/run vs. canonical command surface.** README documents a manual
   `install.sh` + `npm --prefix frontend run build` + `AGENTFLOW_PORT=8787 .venv/bin/python -m agentflow`
   flow, while the [Makefile](../../Makefile) is the stated single command surface
   (`make setup|dev|verify|test|build`). Both are correct but the relationship (Makefile
   wraps the scripts) is not stated in README; OPERATIONS.md is the more complete source.

4. **README "Packages Installed By The App" omits installed dev/QA tools.** README lists
   "Dev/test support: pytest" but the dev extra also installs ruff, mypy, pytest-cov, and
   pip-audit ([pyproject.toml](../../pyproject.toml)). Minor staleness.

5. **NEXT_STEPS.md predates the pillar work.** It lists "Better streaming logs
   (SSE/WebSocket instead of polling)" and "Robust pseudo-terminal support" as future work,
   but SSE streaming, the event bus, and PTY terminals are now implemented
   (`event_bus.py`, `terminal_service.py`, `routes_terminals.py`). NEXT_STEPS.md reads as a
   pre-hardening backlog and conflicts with the current state described in PILLARS.md.

6. **`orchestrator-backend/` is a target spec, not current architecture.** Its README states
   it "defines the final controller backend target". It overlaps with — and in places
   describes a more elaborate model than — the shipped `workflow.py` / `queue_service.py` /
   `task_service.py`. ARCHITECTURE.md already flags this divergence; new docs must not cite
   `orchestrator-backend/*` as a description of present behavior.

## 7. Missing documentation

- **No top-level docs index / table of contents.** README links a subset of `docs/`;
  there is no single map of all 20+ docs and their status (design note vs. authoritative
  vs. target spec).
- **No per-route API reference.** The 10 routers ([backend/agentflow/api/](../../backend/agentflow/api/))
  and the `/api/health` shape are only discoverable via FastAPI `/docs`; there is no
  written endpoint inventory.
- **No documentation for the newly added modules** flagged for this pass:
  `headroom_service.py`, `contracts.py`, `origins.py` (backend) and `lib/ansi.ts`,
  `lib/streamEvent.ts`, `hooks/useAutoScroll.ts`, `components/ErrorBoundary.tsx` (frontend).
  Headroom/contracts/origins have strong in-file docstrings but no narrative doc tying them
  to the pillars.
- **No feature-status matrix.** Nothing classifies each feature as
  Implemented / Partially implemented / Mocked / Experimental / Planned / Deprecated, which
  is needed to reconcile DESIGN.md and NEXT_STEPS.md against the code.
- **No CONTRIBUTING / onboarding doc** beyond ENGINEERING_STANDARDS.md.
- **No documentation of the JSON state-file schemas** (`config.json`, `events.json`,
  `runs.json`, `approvals.json`, `queue.json`, `chat.json`, `usage.json`); ARCHITECTURE.md
  describes them in prose but there is no field-level reference.

## 8. Ambiguous areas (need code confirmation before documenting)

- **Provider naming**: code uses provider id `antigravity` with executables `["agy",
  "antigravity"]` and `loginCommand: "agy"` ([provider_probe.py](../../backend/agentflow/provider_probe.py));
  the memory/README also use "antigravity" and "agy". `AGENT_PROVIDER_IDS` is
  `["codex", "claude", "antigravity"]`. Docs should use these exact ids, not "agy" as the id.
- **Gemini vs. Antigravity for QA role**: [workflow.py](../../backend/agentflow/workflow.py)
  defines the `gemini_qa` step (label "QA / Test", role "qa") and writes `05_QA_RESULTS.md`,
  but the provider set and README describe Antigravity as the QA/controller CLI. The
  mapping of the `gemini_qa` step id to an actual provider needs confirmation in
  `routing_service.py`/`policy_service.py` before documenting the workflow.
- **`FULL_SEQUENCE` excludes `claude_fix`**: `STEP_DEFS` has five steps but `FULL_SEQUENCE`
  is four (`codex_spec, claude_implement, gemini_qa, codex_review`) — `claude_fix` is
  conditional. Worth documenting explicitly to avoid implying a fixed 5-step pipeline.
- **Single-port mode vs. dev mode**: docs must be precise that `:5180` only exists with the
  Vite dev server and proxies to `:8787`; the built app is `:8787` only.
- **`dist/` and `dist-app/` at repo root** (plus `frontend/dist`): which is canonical for
  single-port serving needs confirmation — `app.py` serves `paths.frontend_dist()`, so
  [paths.py](../../backend/agentflow/paths.py) is the authority, not the root `dist/`.
- **Preview routes** (`routes_preview.py`, `PreviewPage.tsx`): a preview/dev-server feature
  exists but its scope (what it previews, lifecycle) is not yet documented.

## 9. Authoritative commands

Same locally and in CI ([Makefile](../../Makefile), [.github/workflows/ci.yml](../../.github/workflows/ci.yml)):

```bash
make setup        # ./scripts/install.sh — create .venv, install backend (editable, dev extras) + frontend deps
make dev          # ./scripts/dev.sh — backend :8787 + Vite dev server :5180
make format       # ruff format backend + npm run format (prettier)
make lint         # ruff check backend + npm run lint (eslint)
make typecheck    # mypy + npm run typecheck (tsc --noEmit)
make test         # backend pytest+coverage AND frontend vitest
make build        # npm run build (tsc && vite build) -> frontend/dist
make verify       # format-check + lint + typecheck + test + build (mirrors CI)
make audit        # pip-audit + npm audit (non-blocking)
make lock         # regenerate requirements.lock from the venv
```

Direct invocations used by the targets / CI:

```bash
.venv/bin/python -m pytest backend/tests --cov=agentflow   # backend tests + coverage (fail_under=55)
npm --prefix frontend run test                              # frontend vitest
AGENTFLOW_PORT=8787 .venv/bin/python -m agentflow           # run the backend (single-port if dist built)
```

CI runs two jobs — `backend` (ruff check, ruff format --check, mypy, pytest+cov, pip-audit)
and `frontend` (eslint, prettier --check, tsc, vitest, build, npm audit). pip-audit and
npm audit are `continue-on-error`.

## 10. Files used as evidence

- Build / config: [pyproject.toml](../../pyproject.toml), [Makefile](../../Makefile),
  [frontend/package.json](../../frontend/package.json),
  [frontend/vite.config.ts](../../frontend/vite.config.ts),
  [.github/workflows/ci.yml](../../.github/workflows/ci.yml), [.env.example](../../.env.example),
  [requirements.lock](../../requirements.lock).
- Backend entry / transport: [backend/agentflow/__main__.py](../../backend/agentflow/__main__.py),
  [app.py](../../backend/agentflow/app.py), [origins.py](../../backend/agentflow/origins.py),
  `api/` routers (10 files), [workflow.py](../../backend/agentflow/workflow.py),
  [agent_commands.py](../../backend/agentflow/agent_commands.py),
  [chat_directives.py](../../backend/agentflow/chat_directives.py),
  [contracts.py](../../backend/agentflow/contracts.py),
  [headroom_service.py](../../backend/agentflow/headroom_service.py),
  [provider_probe.py](../../backend/agentflow/provider_probe.py).
- Frontend: [frontend/src/App.tsx](../../frontend/src/App.tsx) (page set), directory
  listings of `components/`, `pages/`, `pages/tasks/`, `lib/`, `hooks/`.
- Docs: every file listed in [§5](#5-existing-documentation-inventory) (read headers/first
  sections) plus full reads of [README.md](../../README.md), [DESIGN.md](../../DESIGN.md),
  [NEXT_STEPS.md](../../NEXT_STEPS.md).
- Scripts: [scripts/headroom.sh](../../scripts/headroom.sh) and the `scripts/` listing.

## 11. Proposed documentation package (Phase 3)

The files to produce/update in the documentation pass, building on the existing set
(linking to — not duplicating — the authoritative docs already present):

1. **`docs/audit/DOCUMENTATION_DISCOVERY.md`** (this file) — discovery inventory.
2. **`docs/FEATURES.md`** — feature-status matrix classifying every feature as
   Implemented / Partially implemented / Mocked / Experimental / Planned / Deprecated,
   reconciling DESIGN.md and NEXT_STEPS.md against the code.
3. **`docs/API.md`** — endpoint inventory for the 10 `/api/*` routers + `/api/health` +
   the terminal WebSocket, with request/response shapes.
4. **`docs/STATE.md`** — field-level reference for the global and per-workspace JSON state
   files and the event-ledger envelope.
5. **`docs/PROVIDERS.md`** — provider ids/executables (`codex`, `claude`, `antigravity`/`agy`),
   detection, install/login hints, and the workflow step → role/provider mapping
   (incl. the `gemini_qa` and `FULL_SEQUENCE` clarifications from [§8](#8-ambiguous-areas-need-code-confirmation-before-documenting)).
6. **`docs/README.md`** (docs index) — a single map of all docs with status labels
   (authoritative / design note / target spec) and a pointer to PILLARS.md.
7. **README.md / NEXT_STEPS.md / DESIGN.md updates** — resolve the product-name conflict,
   correct the installed-packages list, and mark superseded NEXT_STEPS items as done.
8. **Module-doc additions** for the newly added backend (`headroom_service.py`,
   `contracts.py`, `origins.py`) and frontend (`lib/ansi.ts`, `lib/streamEvent.ts`,
   `hooks/useAutoScroll.ts`, `components/ErrorBoundary.tsx`) units — folded into
   ARCHITECTURE.md / PILLARS.md rather than as standalone files where they fit.
