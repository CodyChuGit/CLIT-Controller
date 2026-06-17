# Final Report — CLIT Controller IDE (AgentComposer) Production Hardening

Branch: `audit/production-hardening` (6 commits, `103 files changed, +6817/-894`).
Companion to [INITIAL_AUDIT.md](INITIAL_AUDIT.md).

## 1. Executive summary

The repository was a high-quality solo local-first tool with **no critical (P0)
defects** but no engineering safety rails and a cluster of real reliability/
security hardening gaps. This pass added the full verification pipeline (lint,
format, type-check, tests, CI) and the documentation deliverables, then fixed all
8 confirmed P1 findings plus the highest-value P2/P3 items — each behavior change
backed by a regression test — while preserving product behavior. Every check now
passes: backend `ruff`/`mypy`/`pytest` (145 tests, 60% coverage), frontend
`eslint`/`tsc`/`vitest` (13 tests) + production build, `pip-audit`, and `npm audit`
(production deps). Work was kept in small, reviewable commits; formatting was
isolated from behavior changes.

## 2. Initial architecture

Local-first FastAPI backend (`backend/agentflow`) + React 18/Vite 5 frontend
(`frontend/src`) orchestrating CLI agents as subprocesses, PTY terminals over
WebSockets, git workspace management, and SSE/polling output streaming. Binds
`127.0.0.1:8787`. Full map in [ARCHITECTURE.md](../ARCHITECTURE.md). The structure
was already coherent (thin routes → services → infrastructure); no architectural
rewrite was warranted or performed.

## 3. Final architecture

Unchanged in shape. Additions are additive and cohesive:
- `agentflow/origins.py` — single source of truth for allowed local origins
  (shared by CORS, the new CSRF guard, and the WebSocket origin check).
- `OriginGuardMiddleware` in `app.py` — CSRF guard on mutating methods.
- `redaction.redact_data` — structured-payload redaction.
- `ProcessRunner` watchdog + retained background-task set.
- Frontend `components/ErrorBoundary.tsx`.
- Engineering rails: `pyproject.toml` tool config, `Makefile`, `.github/workflows/ci.yml`,
  `requirements.lock`, frontend ESLint/Prettier/Vitest, `.env.example`.

## 4. P0–P3 findings

From the audit: **0 P0 · 11 P1 · 31 P2 · 43 P3** (85 total). All 11 P1s were
adversarially verified (8 confirmed, 3 down-adjusted, 0 rejected). Full register in
[INITIAL_AUDIT.md → Appendix A](INITIAL_AUDIT.md#appendix-a--full-findings-register).

## 5. Findings fixed

**All 8 confirmed P1s:**
| ID | Fix |
|----|-----|
| P1-05 | Auto-run policy: code-runners (interpreters/`make`/`npx`/`awk`/`sed`) routed through approval; `git -c`/`tar` exec hooks hard-denied. |
| P1-02 | `redact_data` applied to event/approval payloads → durable `events.json`, SSE stream, and approvals display are scrubbed (raw action kept on-disk only for replay). |
| P1-03 | `max_runtime` watchdog (20 min) on all agent runs; preview server deliberately exempt. |
| P1-04 | `RUNNER.cancel_all()` on shutdown — no more orphaned agent/dev-server process groups. |
| P1-09 | `OriginGuardMiddleware` rejects foreign-origin mutating requests (CSRF). |
| P1-08 | React `ErrorBoundary` around app, per-view, and ChatPanel. |
| P1-10 | Terminal WebSocket Origin/close-code tests added. |
| P1-11 | Process cancel + timeout-reaping tests added. |

**Adjusted P1s:** P1-06→P2 (httpx added to dev extras) ✓; P1-07→P3 (stale
editable venv re-registered as `clit-controller-ide`) ✓.

**P2/P3 fixed:** P2-10/P3-39 (CORS port + unified origins), P2-11 (provider
validation), P2-22 (git `.env` guard), P2-23 (lockfile), P2-24 (version bounds),
P2-26 (CI + tooling), P2-28 (frontend test infra), P2-29 (hermetic test fixture),
P2-31 (stale test), P3-12 (retained background tasks), P3-26 (leaked reference),
P3-42 (coverage tooling). P3-34/P3-37 were confirmed safe (no action needed).

## 6. Findings not fixed (recorded honestly)

Deferred deliberately — either larger refactors with real regression risk and no
active defect, or low-value cleanups. Recommended next, not done now:

- **P1-01 / P2-07 — Unsynchronized JSON ledger writes** (lost-update race between
  the threadpool and the dispatcher). Real but rare and largely self-correcting for
  one user; fix is a per-workspace lock (cx=L). Highest-priority remaining item.
- **P2-02/06/08/12 — blocking file I/O on the event loop / curated child env.**
- **P2-05 — restart recovery leaks a still-alive agent process** (complements
  P1-04 for the crash case; needs pid-reuse-safe killing).
- **P2-14/15/16 — frontend runtime response validation, request cancellation,
  preview-iframe sandbox.**
- **P2-18 — oversized components (ChatPanel/TasksPage) → extract hooks.**
- **P2-19/20/21 — accessibility: command-palette focus trap, `aria-live` for
  streaming replies, ARIA-widget keyboard support.**
- **P2-25/27 — project naming sprawl; redundant launcher/bundle scripts.**
- **P2-30, P3-43 — provider-install test isolation; HTTP-level route tests.**
- Remaining low-risk P3 items (see Appendix A).

## 7. Security improvements

- Prompt-injection-to-RCE surface narrowed: dangerous auto-run vectors now require
  explicit approval or are denied (P1-05).
- Secrets no longer leak into the durable event ledger, the live SSE stream, or the
  approvals display (P1-02).
- CSRF guard on all mutating endpoints; CORS/WS/CSRF origins unified and the stale
  `:5173` corrected to `:5180` (P1-09, P2-10, P3-39).
- Chat provider validated against the allow-list before launch (P2-11).
- Git `file-diff` can no longer surface `.env` contents (P2-22).
- Threat model, controls, and residual risks documented in [SECURITY.md](../SECURITY.md);
  decision recorded in [ADR 0001](../adr/0001-auto-run-policy-allowlist.md).

## 8. Reliability improvements

- Agent runs can no longer hang forever and deadlock the autonomous queue (P1-03).
- In-flight runs are cancelled on shutdown rather than orphaned (P1-04).
- Fire-and-forget background tasks are retained against GC (P1-12).

## 9. Accessibility improvements

- App-wide and per-pane error boundaries provide a recoverable failure state
  instead of a blank screen (P1-08). Deeper a11y items (focus trap, `aria-live`,
  ARIA keyboard) are documented as remaining work (P2-19/20/21).

## 10. Test coverage added

- Backend: 119 → **145 tests** (60% coverage). New suites: terminal WebSocket
  gating (`test_routes_terminals`), process cancel/timeout (`test_process_cancel`),
  payload redaction (`test_redaction_payloads`), CSRF (`test_csrf`), provider/`.env`
  hardening (`test_hardening`), expanded policy tests; plus a hermetic
  `conftest.py` autouse fixture isolating the suite from `~/.agentflow`.
- Frontend: 0 → **13 tests** (Vitest + Testing Library): `taskFormat` helpers,
  `Markdown` XSS-safety, `ErrorBoundary` behavior.

## 11. Developer-experience improvements

- `make setup|dev|format|lint|typecheck|test|build|verify` (same commands locally
  and in CI). `.env.example`, lockfile, and the full docs set under `docs/`.

## 12. Dependency changes

- Added dev tooling: `ruff`, `mypy`, `pytest-cov`, `httpx`, `pip-audit` (backend);
  `eslint`, `prettier`, `vitest`, `@testing-library/*`, `jsdom`, `typescript-eslint`
  (frontend). Added version upper bounds to runtime deps; generated
  `requirements.lock`. No runtime dependency was upgraded or removed.

## 13. Commands executed

`pip install -e ".[dev]"`, `ruff check`/`ruff format`, `mypy`, `pytest --cov`,
`pip-audit`, `npm install`/`npm ci`, `eslint`, `prettier`, `tsc`, `vitest run`,
`npm run build`, `npm audit`, plus secret/conflict/debug scans.

## 14. Verification results

| Check | Result |
|-------|--------|
| ruff lint (backend) | ✅ clean |
| ruff format --check | ✅ 64 files formatted |
| mypy (backend/agentflow) | ✅ no issues (37 files) |
| pytest + coverage | ✅ 145 passed, 60% (gate 55%) |
| backend import smoke | ✅ `agentflow.app` loads |
| pip-audit | ✅ no known vulnerabilities |
| eslint (frontend) | ✅ 0 errors (10 advisory warnings) |
| prettier --check | ✅ clean |
| tsc --noEmit | ✅ clean |
| vitest | ✅ 13 passed |
| frontend build | ✅ built |
| npm audit (prod) | ✅ 0 vulnerabilities |
| secret / conflict / debug scan | ✅ none found |

## 15. Remaining risks

- **Ledger write race (P1-01/P2-07)** — top remaining correctness item.
- **Crash-time agent-process orphaning (P2-05)** — clean shutdown is covered; a
  hard crash can still leak a process.
- **Frontend trusts backend responses (P2-14)** — no runtime schema validation.
- **Dev-only `esbuild`/`vite` advisory (P3-23)** — not in the production bundle;
  fix requires a breaking Vite major upgrade.
- **WebSocket allows missing Origin (P3-38)** and **unauthenticated `/docs` (P3-40)**
  — accepted for a loopback single-user tool; documented in SECURITY.md.

## 16. Recommended next actions

1. Add a per-workspace lock around ledger read-modify-write (P1-01/P2-07).
2. Offload the dispatcher tick's file I/O off the event loop (P2-08/P2-12).
3. Introduce runtime validation (zod) at the `api.ts` boundary, starting with the
   `StreamEvent` path (P2-14), and per-request stale-guarding (P2-15).
4. Address the a11y trio (P2-19/20/21).
5. Reap the still-alive agent process during restart recovery (P2-05).
6. Reconcile project naming and consolidate the redundant launcher scripts
   (P2-25/27).
