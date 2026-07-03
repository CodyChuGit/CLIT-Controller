# Troubleshooting

Use this guide for common local failures. Commands run from the repository root.

## Backend Is Not Reachable

Check the backend port:

```bash
lsof -nP -tiTCP:8787 -sTCP:LISTEN
curl http://localhost:8787/api/health
```

Restart with:

```bash
./scripts/dev.sh
```

`dev.sh` frees ports `8787` and `5180` before starting.

## No Workspace Selected

Workspace-scoped routes return HTTP 409 until a workspace is selected.

Fix: open Projects and choose a workspace. State will be written under
`<workspace>/.agentflow/`.

## Provider CLI Missing

Check the Agents page or run:

```bash
command -v claude codex agy
```

Install the missing provider and rerun the Agents check. Antigravity may require
`~/.local/bin` on `PATH`.

## Controller Output Does Not Take Action

The controller mutates state only through a valid `CLITC_RESULT_V1` block.

Check:

- Agent Dock transcript for a validation failure card.
- Logs for `controller.result_invalid`.
- Events through `/api/events?cursor=0`.

Invalid result blocks intentionally mutate no state. If no `CLITC_RESULT_V1`
block exists, the backend can fall back to legacy `agentflow-*` directives and
emits `controller.legacy_directives`.

## Live Output Is Not Streaming

Managed runs stream through:

- SSE: `/api/events/stream`
- polling fallback: `/api/events?cursor=<id>`

Check the Logs page for active runs and inspect the run record:

```bash
curl http://localhost:8787/api/runs/<run_id>
```

If a provider produces output only at process exit, the UI cannot show chunks
before the CLI emits them. For Claude, the default template uses `--output-format
stream-json`, which is normalized before display.

## Provider Terminal Stuck

Provider tabs use PTY WebSockets. Check diagnostics:

```bash
curl http://localhost:8787/api/terminals/antigravity/diagnostics
curl http://localhost:8787/api/terminals/codex/diagnostics
curl http://localhost:8787/api/terminals/claude/diagnostics
```

Use the terminal restart button or:

```bash
curl -X POST http://localhost:8787/api/terminals/antigravity/kill
```

After an unclean backend exit, restart the backend. Startup sweeps recorded PTY
pidfiles under `~/.agentflow/run/terminals/`.

## Queue Is Blocked

Open Tasks or query:

```bash
curl http://localhost:8787/api/queue
curl 'http://localhost:8787/api/approvals?pendingOnly=true'
```

Common causes:

- approval pending
- provider busy
- provider missing
- previous step failed
- item was intentionally blocked by policy

Use approve, reject, retry, skip, reroute, or remove from the Tasks queue strip.

## Headroom Not Applying

Headroom is enabled by default but fail-open. If the proxy is missing or
unreachable, `claude` and `codex` run directly.

Check port `8799`:

```bash
lsof -nP -tiTCP:8799 -sTCP:LISTEN
```

Install when desired:

```bash
pip install "headroom-ai[all]"
```

Do not point Headroom at `8787`; that is the app backend.

## Preview Does Not Load

Open Preview and check the configured command and URL. The backend strips
`PORT` and `AGENTFLOW_PORT` from child process environments so preview servers do
not bind over the app backend.

Use:

```bash
curl http://localhost:8787/api/preview/check
```

## State Looks Stale After A Crash

Restart the backend. Workspace recovery settles stale running runs, queue items,
and task steps. PTY session cleanup runs at startup.

If a process is clearly orphaned:

```bash
pgrep -fl 'codex|claude|agy|headroom|uvicorn|vite'
```

Prefer app controls before manually killing processes.
