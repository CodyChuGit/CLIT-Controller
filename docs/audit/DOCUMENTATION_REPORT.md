# Documentation Package Report

Final report for the documentation + production-hardening pass on
`audit/production-hardening`. Companion to
[DOCUMENTATION_DISCOVERY.md](DOCUMENTATION_DISCOVERY.md),
[INITIAL_AUDIT.md](INITIAL_AUDIT.md), and [FINAL_REPORT.md](FINAL_REPORT.md).

## Executive summary

The repository now has a complete, code-derived documentation package and an
explicit statement of its five product pillars ([PILLARS.md](../PILLARS.md)) that
the test suites encode as success metrics. Documentation was written by inspecting
the actual code, configuration, scripts, and tests; feature status is classified
honestly; every repo-relative link was verified to resolve. Overall documentation
health: **ready for new contributors**.

## Repository understanding

CLIT Controller IDE is a local-first, single-user macOS-oriented cockpit that
orchestrates CLI coding agents (claude/codex/agy) as subprocesses, runs PTY
terminals over WebSockets, manages a git workspace, and streams agent output live
via SSE + polling. FastAPI backend (`backend/agentflow`, `127.0.0.1:8787`) + React
18/Vite 5 frontend (`frontend/src`, dev `:5180`). State is plaintext JSON ledgers
under `~/.agentflow` and `<workspace>/.agentflow` — no database. See
[ARCHITECTURE.md](../ARCHITECTURE.md) and [PILLARS.md](../PILLARS.md).

## Files created

| File | Purpose |
|------|---------|
| [docs/INDEX.md](../INDEX.md) | Audience-organized documentation map. |
| [docs/PILLARS.md](../PILLARS.md) | The five product pillars + interaction model (success metrics). |
| [docs/PRODUCT_OVERVIEW.md](../PRODUCT_OVERVIEW.md) | What the product is, for whom, main workflows. |
| [docs/FEATURE_STATUS.md](../FEATURE_STATUS.md) | Honest feature matrix with evidence. |
| [docs/GETTING_STARTED.md](../GETTING_STARTED.md) | Clone → install → run. |
| [docs/DEVELOPMENT.md](../DEVELOPMENT.md) | Workflow, commands, maintenance matrix, AI-agent handoff. |
| [docs/REPOSITORY_STRUCTURE.md](../REPOSITORY_STRUCTURE.md) | Curated tree + placement guidance. |
| [docs/FRONTEND.md](../FRONTEND.md) | React/Vite app guide. |
| [docs/BACKEND.md](../BACKEND.md) | FastAPI backend guide. |
| [docs/API.md](../API.md) | HTTP/SSE/WebSocket endpoint inventory. |
| [docs/DATA_MODEL.md](../DATA_MODEL.md) | JSON-ledger persistence model. |
| [docs/CONFIGURATION.md](../CONFIGURATION.md) | Env vars + file-based config. |
| [docs/TESTING.md](../TESTING.md) | Test strategy + commands. |
| [docs/TROUBLESHOOTING.md](../TROUBLESHOOTING.md) | Symptom/cause/fix. |
| [docs/LIMITATIONS.md](../LIMITATIONS.md) | Material limitations by area. |
| [docs/ROADMAP.md](../ROADMAP.md) | Proposed next work (evidence-derived). |
| [docs/GLOSSARY.md](../GLOSSARY.md) | Project-specific terms. |
| [docs/AI_AGENT_GUIDE.md](../AI_AGENT_GUIDE.md) | Deterministic handoff for AI agents. |
| [CONTRIBUTING.md](../../CONTRIBUTING.md), [CHANGELOG.md](../../CHANGELOG.md) | Contribution guide + changelog. |
| [docs/audit/DOCUMENTATION_DISCOVERY.md](DOCUMENTATION_DISCOVERY.md) | Discovery inventory. |

(ARCHITECTURE/OPERATIONS/SECURITY/ENGINEERING_STANDARDS, the audit reports, and
ADR 0001 were created in the earlier audit pass and are linked, not duplicated.)

## Files updated

- [README.md](../../README.md) — routes into the docs index; adds the Headroom note.
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) — corrected the CORS origin (`:5173`→`:5180`)
  and the shared `origins.py`/CSRF guard; fixed a sibling link.
- [docs/FRONTEND.md](../FRONTEND.md) — linked the now-present `LIMITATIONS.md` and
  the repo-root `DESIGN.md`.
- [docs/CONFIGURATION.md](../CONFIGURATION.md) — rebased repo-root-relative links to
  `docs/`-relative.

## Existing inaccuracies corrected

- CORS allowlist documented as `:5173` (the pre-hardening value); the code now uses
  `:5180` via `origins.py`. Corrected in ARCHITECTURE.md.
- A few generated docs initially used repo-root-relative or `../`-mismatched links
  (parallel authoring); all were rebased and verified.
- `DESIGN.md` and `LIMITATIONS.md` were briefly referenced as absent (a concurrent
  authoring race); both exist and are now linked.

## Feature classification

Implemented & tested: workspace/file/git surfaces, provider detection, orchestrator
chat + directives, task orchestration + queue + dispatcher, approvals, live event
streaming, PTY terminals, preview dev-server, usage/budget, Headroom token saving
(opt-in), deterministic contracts. Partial: full CLI-output normalization, a11y
keyboard/focus patterns, auto-scroll consolidation, native structured controller
output. Experimental/optional: `omlx`/`ollama` local providers, voice I/O (design
note only). See [FEATURE_STATUS.md](../FEATURE_STATUS.md).

## Commands verified

Executed successfully during this pass:
- `ruff check backend`, `ruff format --check backend`, `mypy` — clean.
- `pytest backend/tests` — **165 passed** (~60% coverage).
- `tsc --noEmit`, `eslint .` (0 errors), `vitest run` — **26 passed**, `npm run build` — built.
- Documentation link check (all repo-relative links resolve).

## Commands not verified

- `headroom proxy` / `scripts/headroom.sh` end-to-end against a live proxy (the
  integration is unit-tested with the probe/injection mocked; a real proxy run was
  not performed in this pass).
- Browser preview of the running UI (the operator's dev servers occupied the ports;
  UI behavior is covered by Vitest + build instead).
- macOS `.app`/PWA bundle builders (`scripts/make-app.sh`, `create-macos-app-mode.sh`).

## Failed verification

None. The pre-existing `test_budget_context_header_format` failure was fixed in the
earlier audit pass.

## Remaining ambiguity

- Some `docs/*.md` design notes (orchestrator-backend, phase-1-5) describe intended
  designs that partly diverge from the implementation; they are linked as historical
  context, and the authoritative behavior is documented in the new package.
- Realized Headroom token savings are environment-dependent; AgentComposer reports
  whether routing was applied, not a measured ratio (verify with
  `headroom agent-savings --check-perf`).

## Remaining documentation debt

- No generated OpenAPI snapshot is committed; [API.md](../API.md) points to the live
  `/docs`. A committed `openapi.json` + drift check is a possible follow-up.
- No Mermaid sequence diagrams beyond the textual flows (kept textual to avoid
  diagram drift).

## Maintenance rules

See the **Documentation maintenance matrix** in [DEVELOPMENT.md](../DEVELOPMENT.md):
each change type lists the docs to update (e.g. new API route → API.md; new env var
→ CONFIGURATION.md + .env.example; new feature → FEATURE_STATUS.md + PRODUCT_OVERVIEW;
pillar-affecting change → PILLARS.md + the pillar tests).

## Final assessment

**Ready for new contributors.** A new engineer can understand, run, test, and safely
modify the repository from the documentation without tribal knowledge. It is not yet
"production operations ready" in the multi-tenant/deployment sense — by design it is a
local single-user tool with no deployment pipeline (documented in
[OPERATIONS.md](../OPERATIONS.md) and [LIMITATIONS.md](../LIMITATIONS.md)).
