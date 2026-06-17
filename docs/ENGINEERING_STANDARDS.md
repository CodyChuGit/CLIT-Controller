# Engineering Standards

The rules this repository must obey. They are specific to **CLIT Controller IDE**
(a local-first FastAPI + React/Vite developer tool that runs CLI coding agents),
not generic enterprise ceremony. Keep them few, enforced, and honest.

## Verification

One command surface, identical locally and in CI (see [Makefile](../Makefile) and
[.github/workflows/ci.yml](../.github/workflows/ci.yml)):

| Task | Backend | Frontend |
|------|---------|----------|
| format | `ruff format backend` | `prettier --write` |
| lint | `ruff check backend` | `eslint .` |
| typecheck | `mypy` | `tsc --noEmit` |
| test | `pytest --cov=agentflow` | `vitest run` |
| build | (import smoke test) | `tsc && vite build` |

Run everything with `make verify`. CI runs the same commands on every push/PR.

## Invariants

These must hold after every change. CI enforces the mechanizable ones.

**Build & run**
- One documented local startup path (`make dev` / `scripts/dev.sh`) and one
  production build path (`make build` → backend serves `frontend/dist`).
- The frontend production build must succeed (`tsc` clean + `vite build`).
- Backend must import and start cleanly (`python -c "import agentflow.app"`).

**Types & lint**
- TypeScript runs in `strict` mode; no new `any` (the codebase currently has
  zero). `eslint` has no errors (Fast-Refresh warnings are advisory).
- `mypy` is clean on `backend/agentflow`. New `# type: ignore`, `Any`, and
  `noqa` need an inline reason.
- `ruff` lint is clean; formatting is owned by `ruff format` / `prettier`.

**Config**
- No secrets in the repo. Runtime config is file-based (`~/.agentflow`,
  `<workspace>/.agentflow`); the only env knobs are documented in
  [.env.example](../.env.example).
- Dependencies are version-bounded in `pyproject.toml` / `package.json` and
  pinned in `requirements.lock` / `package-lock.json`.

**Backend correctness & safety**
- The server binds `127.0.0.1` only.
- No `shell=True`; subprocesses are spawned with explicit `argv` lists.
- No user/agent-controlled filesystem path without a workspace-containment check.
- No silent exception swallowing. Broad `except Exception` is allowed only at a
  boundary that genuinely must not crash (startup recovery, background loops,
  best-effort logging) and must be annotated (`# noqa: BLE001 — reason`).
- Every network/subprocess call has an explicit timeout, **except** intentionally
  long-lived processes (agent runs, the preview dev server), which instead have a
  cancellation path and a generous watchdog.
- No unbounded retry loop; no unbounded in-memory buffer (logs, events, runs,
  PTY scrollback are all capped).
- Secrets are never persisted or broadcast: all log/event/ledger output passes
  through `redaction.redact` (including structured event payloads).

**Frontend correctness & resilience**
- Network access is centralized in `api.ts`; responses crossing the trust
  boundary are validated or defensively handled, never assumed well-formed.
- Every route-level view has a React error boundary so one failure cannot
  white-screen the app.
- Important workflows have intentional loading / empty / error / retry states.

**Testing**
- The suite is hermetic (no reads/writes to the real `~/.agentflow`; see
  `backend/tests/conftest.py`) and deterministic (no `sleep`-based timing hacks —
  poll with a timeout).
- Coverage must not regress below the `fail_under` gate in `pyproject.toml`.
- Every fixed defect gets a regression test.

## Calibration notes

- This is a **single-user local tool**. "No authentication" is by design, not a
  P0 — the security boundary is the loopback interface plus origin checks, not a
  login. See [SECURITY.md](SECURITY.md).
- Prefer the smallest coherent change. Do not combine repo-wide reformatting with
  behavior changes; formatting lands in its own commit.
- Type strictness is calibrated to surface real `Optional`/`None` bugs without
  demanding full annotations on the many dynamically-shaped JSON dicts. Tighten
  incrementally (a reasonable next step: `noUncheckedIndexedAccess` in the
  frontend; per-module mypy `disallow_untyped_defs`).
