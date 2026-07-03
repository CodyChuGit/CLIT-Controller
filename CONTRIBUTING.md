# Contributing

CLIT Controller IDE is a local-first UI for CLI coding agents. Keep changes
small, verified, and aligned with the current docs.

## Setup

```bash
make setup
make dev
```

Open `http://localhost:5180`.

## Checks

Run focused checks while editing:

```bash
.venv/bin/python -m pytest backend/tests/test_controller_protocol.py
npm --prefix frontend run test -- src/lib/liveActivity.test.ts
```

Run the full gate before broad handoff:

```bash
make verify
```

## Code Rules

- Put backend behavior in services, not thick routes.
- Use explicit argv subprocess execution, never `shell=True`.
- Keep workspace file operations confined to the selected workspace.
- Keep frontend HTTP access in `frontend/src/api.ts`.
- Keep live output in the shared event stream.
- Keep provider PTYs in the terminal service and Agent Dock surfaces.
- Use `CLITC_RESULT_V1` for controller mutations.
- Redact secrets before persistence or broadcast.

## Docs Rules

When behavior changes, update the matching docs in the same change:

- routes: `docs/API.md`
- backend behavior: `docs/BACKEND.md`, `docs/ARCHITECTURE.md`
- frontend behavior: `docs/FRONTEND.md`, `DESIGN.md`
- config/routing/templates: `docs/CONFIGURATION.md`
- state files: `docs/DATA_MODEL.md`
- safety/policy: `docs/SECURITY.md`
- setup/runtime: `docs/GETTING_STARTED.md`, `docs/OPERATIONS.md`

Remove stale planning markdown once its useful content has been folded into the
current reference docs.

## Security

This app runs user-owned CLIs and local commands. Before touching process,
terminal, path, policy, origin, or redaction code, read
[docs/SECURITY.md](docs/SECURITY.md).

Never commit secrets or provider credentials.
