# Engineering Standards

These are the rules that keep CLIT Controller IDE reliable as a local agent
orchestration tool.

## Verification

Use the smallest reliable check while editing and the full gate for broad work.

| Stage | Backend | Frontend |
| --- | --- | --- |
| format | `ruff format backend` | `npm --prefix frontend run format` |
| lint | `ruff check backend` | `npm --prefix frontend run lint` |
| typecheck | `mypy` | `npm --prefix frontend run typecheck` |
| test | `.venv/bin/python -m pytest backend/tests` | `npm --prefix frontend run test` |
| build | import smoke / package checks | `npm --prefix frontend run build` |

Full gate:

```bash
make verify
```

## Backend Invariants

- Bind to localhost.
- Keep routers thin; put business logic in services.
- Spawn subprocesses with explicit argv lists, never `shell=True`.
- Validate workspace paths before file operations.
- Redact secrets before persistence or broadcast.
- Keep live managed output on the shared event bus.
- Keep PTY terminal lifecycle in `terminal_service.py`.
- Use durable state ledgers for runs, events, approvals, queue, and tasks.
- Settle stale running state on startup.
- Route risky commands through policy and approvals.

## Controller Invariants

- `CLITC_RESULT_V1` is the primary controller mutation protocol.
- A valid result executes one validated action.
- An invalid result emits a failure event and mutates no state.
- Legacy `agentflow-*` directives are fallback only when no structured block is
  present.
- Controller actions must stay explicit and auditable.

## Frontend Invariants

- `frontend/src/api.ts` is the normal HTTP boundary.
- `frontend/src/stream.tsx` owns SSE/polling live events.
- `TerminalPane.tsx` owns provider PTY WebSockets.
- Agent Dock and Tasks should render live output from the same event store.
- Provider terminals live in Agent Dock in the current navigation.
- Raw output belongs behind drill-down views when a structured summary exists.
- Keep loading, empty, error, retry, and disconnected states visible.

## Security Invariants

- No secrets in the repository.
- Provider credentials stay with provider CLIs.
- Foreign origins cannot mutate app state or open terminal sockets.
- Commands that change remote/shared state require approval.
- Hard-denied command shapes do not run.
- Broad exception handling is only acceptable at must-not-crash boundaries and
  needs a clear reason.

## Documentation Invariants

- Docs describe the current working app, not old plans.
- Remove obsolete planning or audit markdown once its useful reference content is
  captured in current docs.
- Update [API.md](API.md), [BACKEND.md](BACKEND.md), [FRONTEND.md](FRONTEND.md),
  [CONFIGURATION.md](CONFIGURATION.md), and [DATA_MODEL.md](DATA_MODEL.md) when
  their corresponding code changes.
