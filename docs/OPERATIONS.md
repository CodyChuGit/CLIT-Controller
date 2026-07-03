# Operations

CLIT Controller IDE is intended to run locally. It binds to localhost, executes
user-owned CLI tools, and stores state on disk.

## Development Run

```bash
./scripts/dev.sh
```

Ports:

- backend: `http://localhost:8787`
- frontend: `http://localhost:5180`

Vite proxies `/api`, SSE, and terminal WebSockets to the backend.

## Production-Style Run

```bash
npm --prefix frontend run build
AGENTFLOW_PORT=8787 .venv/bin/python -m agentflow
```

Then open `http://localhost:8787`.

## Startup

On startup the backend:

1. recovers the current workspace if one is selected
2. sweeps orphaned PTY terminal sessions
3. compresses bulky prompt context via the embedded Headroom library (no proxy process)
4. starts the queue dispatcher

## Shutdown

On graceful shutdown the backend:

- cancels active managed runs
- terminates PTY sessions
- stops the queue dispatcher

If the backend crashes, the next startup settles stale run/queue/task state and
sweeps terminal pidfiles.

## Runtime State

| Location | Purpose |
| --- | --- |
| `~/.agentflow/config.json` | Global settings and current workspace. |
| `~/.agentflow/providers.json` | Provider probe/install cache. |
| `~/.agentflow/run/terminals/` | PTY pidfiles for orphan cleanup. |
| `<workspace>/.agentflow/` | Workspace chat, events, runs, queue, approvals, tasks, logs, usage. |

## Long-Running Processes

Managed runs are owned by `process_runner.py` and tracked by run id. Examples:

- controller/provider chat
- task steps
- shell commands
- preview server
- Headroom in-process compression

Interactive terminals are PTY sessions owned by `terminal_service.py`.

## Logs

The Logs page reads redacted log entries from backend state. Run logs are written
under task log folders or the workspace app directory depending on the run.

Secrets are redacted before persistence and broadcast.

## Headroom

Headroom is enabled by default and fail-open. If installed, the backend manages
the proxy process. If not installed or unreachable, `claude` and `codex` run
directly.

Install when desired:

```bash
pip install "headroom-ai[all]"
```

## Provider CLIs

CLIT Controller does not install provider CLIs automatically at startup. Use the
Agents page to check, install, or launch login helpers.

Provider auth remains with each official CLI.

## Force Cleanup

If a process survives an unclean shutdown:

```bash
pgrep -fl 'codex|claude|agy|headroom|uvicorn|vite'
```

Prefer app controls first: Stop, Restart terminal, or backend restart. Only kill
manual processes when they are clearly orphaned.
