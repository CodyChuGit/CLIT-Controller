# Contributing

Thanks for working on **CLIT Controller IDE** (AgentComposer) — a local-first,
single-user developer cockpit that orchestrates CLI coding agents. This page is the
short, actionable checklist. The full contributor playbook (how to add a route,
service, contract, page, or test) lives in
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) and is not repeated here.

## Setup

```bash
make setup        # creates .venv (Python 3.11+), installs backend + frontend deps
make dev          # backend :8787 + Vite dev server :5180 (develop against :5180)
```

The macOS system `python3` is 3.9 and will not work — `make setup` finds a Python
≥ 3.11. See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for the dev-server and
hot-reload details.

## Branches & commits

- `main` is the only long-lived branch. Branch off `main`, keep each change small
  and coherent, and open a pull request.
- Commit subjects are **descriptive** (imperative, what + why), e.g.
  `Pillar 5: deterministic, versioned output contracts`. Conventional-commit
  prefixes are welcome but not required.
- End every commit message with the trailer:

  ```text
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

- **Do not mix repo-wide reformatting with behavior changes** — formatting lands in
  its own commit.

## Required checks

One command, identical locally and in CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)):

```bash
make verify       # format-check + lint + typecheck + test + build
```

All must be green before a PR merges:

| | Backend | Frontend |
|--|---------|----------|
| format-check | `ruff format --check` | `prettier --check` |
| lint | `ruff check` | `eslint` |
| typecheck | `mypy` | `tsc --noEmit` |
| test | `pytest --cov=agentflow` | `vitest run` |
| build | (import smoke via tests) | `tsc && vite build` |

If `make verify` is green locally, CI will be too. Coverage must not drop below the
`fail_under` gate in [pyproject.toml](pyproject.toml).

## Code style

- **Formatting is owned by tooling**, not by hand: `ruff format` (backend) and
  `prettier` (frontend). Run `make format` before committing.
- Backend lint/style follows `ruff` (line-length 120). Frontend follows `eslint`.
- **One markdown renderer** — [Markdown.tsx](frontend/src/components/Markdown.tsx).
  Do not introduce a second.
- **No `shell=True`** — subprocesses spawn with explicit `argv` lists.
- **Loopback only** — the server binds `127.0.0.1`; there is no auth by design.
- Centralize frontend network access in [api.ts](frontend/src/api.ts); components
  never `fetch` directly.

## Type safety

- TypeScript runs in `strict` mode. **No new `any`** (the codebase has zero).
- `mypy` must be clean on `backend/agentflow`. A new `# type: ignore`, `Any`, or
  `noqa` needs an inline reason.

## Testing

- **Every fixed defect gets a regression test in the same PR**, and new behavior
  ships with a test.
- The backend suite is **hermetic** (the autouse fixture in
  [backend/tests/conftest.py](backend/tests/conftest.py) redirects `~/.agentflow`
  and `$HOME` to a temp dir — never touch real global state) and **deterministic**
  (poll with a timeout, no `sleep`-based timing).
- The five product pillars are the success metrics — see
  [docs/PILLARS.md](docs/PILLARS.md). A change that improves one pillar while
  materially weakening another needs explicit justification in the PR.

## Documentation

When you change something with a documentation footprint, update the relevant docs
in the **same PR**. Use the **documentation maintenance matrix** in
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) to find which doc to touch (new route or
service → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); new env var → `.env.example`
+ [docs/OPERATIONS.md](docs/OPERATIONS.md); origin/CORS/subprocess changes →
[docs/SECURITY.md](docs/SECURITY.md); etc.).

## Security

This tool runs CLI agents and shells as subprocesses, so containment matters. Read
[docs/SECURITY.md](docs/SECURITY.md) before touching security-sensitive areas
([process_runner.py](backend/agentflow/process_runner.py),
[policy_service.py](backend/agentflow/policy_service.py),
[workspace.py](backend/agentflow/workspace.py),
[origins.py](backend/agentflow/origins.py)). Keep these invariants intact:

- Loopback-only bind; no secrets in the repo.
- No `shell=True`; every user/agent-controlled path gets a workspace-containment
  check.
- All log/event/ledger output passes through
  [redaction.py](backend/agentflow/redaction.py), including structured payloads.
- No unbounded buffers or retry loops; no silently swallowed exceptions (a broad
  `except` at a must-not-crash boundary needs an annotated reason).

Report issues via the repository's issue tracker. Do not include real secrets or
exploit-ready details in public reports.

## Dependency policy

- Dependencies are **version-bounded** in [pyproject.toml](pyproject.toml) /
  [frontend/package.json](frontend/package.json) and **pinned in lockfiles**:
  [requirements.lock](requirements.lock) and
  [frontend/package-lock.json](frontend/package-lock.json).
- Adding a dep means bounding it and updating the lockfile (`make lock` regenerates
  the Python lockfile; `npm install` updates `package-lock.json`). Commit the
  lockfile change.
- No secrets in any dependency config. `make audit` runs the vulnerability scans.

## Review checklist

Before requesting review, confirm:

- [ ] Branched off `main`; change is the smallest coherent unit.
- [ ] `make verify` is green (format-check · lint · typecheck · test · build).
- [ ] Business logic lives in a service, not a route; output meaning is a versioned
      contract ([contracts.py](backend/agentflow/contracts.py)), not re-parsed prose.
- [ ] New behavior tested; every fixed bug has a regression test.
- [ ] No new `any` (frontend) and no unexplained `# type: ignore` / `Any` / `noqa`
      (backend).
- [ ] Security invariants intact (loopback bind, no `shell=True`, workspace-contained
      paths, redacted output, bounded buffers).
- [ ] Docs updated per the maintenance matrix.
- [ ] Formatting commit is separate from behavior commits.

## Definition of done

A change is done when `make verify` passes locally and CI is green; it is the
smallest coherent unit with formatting kept separate; new behavior and every fixed
bug are covered by tests; type and security invariants hold; and the docs called out
by the maintenance matrix are updated. See the fuller statement in
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
