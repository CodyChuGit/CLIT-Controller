# Testing

Run focused checks while developing and the full gate before broad changes.

## Backend

```bash
.venv/bin/python -m pytest backend/tests
```

Useful targeted checks:

```bash
.venv/bin/python -m pytest backend/tests/test_controller_protocol.py
.venv/bin/python -m pytest backend/tests/test_chat_service.py
.venv/bin/python -m pytest backend/tests/test_streaming.py
.venv/bin/python -m pytest backend/tests/test_terminal_service.py backend/tests/test_routes_terminals.py
.venv/bin/python -m pytest backend/tests/test_task_service.py backend/tests/test_queue_service.py
```

Backend tests are hermetic. `backend/tests/conftest.py` redirects global state so
tests do not touch the developer's real `~/.agentflow/`.

## Frontend

```bash
npm --prefix frontend run test
```

Useful targeted checks:

```bash
npm --prefix frontend run test -- src/lib/liveActivity.test.ts
npm --prefix frontend run test -- src/pages/tasks/TaskDispatchMap.test.tsx
npm --prefix frontend run test -- src/components/conversation/ConversationView.test.tsx
```

## Static Checks

```bash
make lint
make typecheck
make format-check
```

## Full Gate

```bash
make verify
```

`make verify` runs format checks, lint, type checks, tests, and the frontend
build. It is the command to use before handing off a broad or risky change.

## Coverage And Risk

- Every fixed defect should get a regression test.
- Controller protocol, streaming, queue dispatch, terminals, approvals, and
  workspace path handling need targeted tests when changed.
- Docs-only changes do not need unit tests, but stale-link and stale-reference
  searches are expected.
