# Getting Started

This is the shortest path from a clean clone to the current working app.

## Prerequisites

- macOS or Linux. macOS is the primary target.
- Python 3.11 or newer.
- Node.js 20 or newer.
- git.
- At least one provider CLI if you want agent runs: `claude`, `codex`, or `agy`.

The app has no database. Runtime state is JSON on disk under `~/.agentflow/` and
`<workspace>/.agentflow/`.

## Install

```bash
git clone https://github.com/CodyChuGit/CLIT-Controller.git
cd CLIT-Controller
./scripts/install.sh
```

`install.sh` creates `.venv`, installs the backend in editable mode with dev
dependencies, and runs `npm install` in `frontend/`.

You can also use:

```bash
make setup
```

## Run In Development

```bash
./scripts/dev.sh
```

Open `http://localhost:5180`.

Ports:

| Service | URL |
| --- | --- |
| Frontend dev server | `http://localhost:5180` |
| Backend API | `http://localhost:8787` |
| API docs | `http://localhost:8787/docs` |
| Health check | `http://localhost:8787/api/health` |

The Vite dev server proxies `/api`, SSE, and terminal WebSockets to the backend.
Restart `./scripts/dev.sh` after backend changes.

## Run Single-Port

```bash
npm --prefix frontend run build
AGENTFLOW_PORT=8787 .venv/bin/python -m agentflow
```

Open `http://localhost:8787`. In this mode the FastAPI backend serves the built
frontend from `frontend/dist`.

## First Run

1. Open Projects and select a workspace.
2. Open Agents and check installed CLIs.
3. Log in to provider CLIs through their own tools when needed.
4. Use the right-hand Agent Dock controller tab to ask for work.
5. Watch task distribution on the Tasks page.

Provider tabs in Agent Dock are real PTY terminals. There is no separate
Terminals page in the current navigation.

## Provider CLIs

Common installs:

```bash
npm install -g @openai/codex
npm install -g @anthropic-ai/claude-code
curl -fsSL https://antigravity.google/cli/install.sh | bash
```

Antigravity commonly installs `agy` into `~/.local/bin`. Make sure that directory
is on `PATH`.

## Common Commands

```bash
make setup
make dev
make test-backend
make test-frontend
make build
make verify
make clean
```

Run the smallest reliable command for the change you made. Use `make verify` for
the full local gate.
