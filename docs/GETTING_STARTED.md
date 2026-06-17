# Getting Started

The shortest verified path from a clean clone to a running app. Every command
below is copyable and listed in execution order with its working directory.

For the deeper picture once you are running, see
[ARCHITECTURE.md](ARCHITECTURE.md), [OPERATIONS.md](OPERATIONS.md), and
[PILLARS.md](PILLARS.md).

## Prerequisites

- **Operating system.** macOS is the primary, fully exercised target. The
  backend, frontend, and test suite run on Linux too, but the app-window helper
  scripts ([scripts/app-mode.sh](../scripts/app-mode.sh),
  [scripts/app.sh](../scripts/app.sh)) call macOS's `open` command to launch a
  browser window — on Linux they will not open a window, so browse to the URL
  manually (everything else works unchanged). Windows is not supported.
- **Python 3.11 or newer.** Setup searches for `python3.13`, `python3.12`,
  `python3.11`, then `python3`, and refuses anything older than 3.11
  (see [scripts/install.sh](../scripts/install.sh)). The project venv lives at
  `.venv`; on macOS the system `python3` may be 3.9, so install a newer one
  (for example `brew install python@3.12`) if setup reports it cannot find 3.11+.
- **Node.js + npm.** Required for the React/Vite frontend
  (see [frontend/package.json](../frontend/package.json)).

There is no database and no authentication: state is plaintext JSON on disk and
the server binds to loopback only.

## 1. Clone

```bash
git clone <repository-url> AgentComposer
cd AgentComposer
```

All later commands run from the repository root (`AgentComposer/`) unless noted.

## 2. Setup (one time)

This creates `.venv`, installs the backend as an editable package with dev
extras (`pip install -e ".[dev]"`), and runs `npm install` in `frontend/`.

**Recommended:**

```bash
# from repository root
make setup
```

`make setup` just calls the install script (see [Makefile](../Makefile)); you
can run the script directly instead:

```bash
# from repository root
./scripts/install.sh
```

Optionally pin a specific interpreter:

```bash
# from repository root
PYTHON=python3.12 ./scripts/install.sh
```

Expected output (abridged):

```
==> Using python3.12 (Python 3.12.x)
==> Creating virtualenv at .venv
==> Installing backend dependencies
==> Installing frontend dependencies
...
✓ Install complete. Start the app with: ./scripts/dev.sh
```

### npm cache permission workaround (handled automatically)

If `npm install` fails (commonly a `~/.npm` permissions issue), the install
script automatically retries with an isolated cache under `$TMPDIR` — you do not
need to do anything. The retry it runs is:

```bash
# what install.sh runs for you on failure (from the frontend/ directory)
npm install --no-fund --no-audit --cache "${TMPDIR:-/tmp}/agentflow-npm-cache"
```

## 3. Run

**Recommended:**

```bash
# from repository root
make dev
```

`make dev` calls [scripts/dev.sh](../scripts/dev.sh), which frees ports 8787 and
5180 if anything is already listening, starts the backend, then starts the Vite
dev server in the foreground. You can run the script directly instead:

```bash
# from repository root
./scripts/dev.sh
```

This starts two processes:

- **Backend** — FastAPI/uvicorn on `http://localhost:8787` (entry point
  `python -m agentflow`, see [backend/agentflow/__main__.py](../backend/agentflow/__main__.py)).
  Override the port with `AGENTFLOW_PORT`.
- **Frontend** — Vite dev server on `http://localhost:5180` with hot reload,
  proxying `/api` to the backend.

### Default URLs

| What | URL |
| --- | --- |
| App (dev, hot reload) | http://localhost:5180 |
| Backend + API (and built frontend, if present) | http://localhost:8787 |
| API docs (Swagger UI) | http://localhost:8787/docs |
| Health check | http://localhost:8787/api/health |

**Use http://localhost:5180 during development.** Port 8787 serves the API and,
only after you run a production build (step below), the built frontend.

### Expected first-run output

`./scripts/dev.sh` prints a banner, then the backend's own banner from
`python -m agentflow`:

```
  Command Line Interface Terminal Controller
  CLIT Controller IDE
  Vibe with CLIT Controller
  Backend  → http://localhost:8787   (API + built frontend, if present)
  Frontend → http://localhost:5180   (dev server, hot reload)

  Command Line Interface Terminal Controller
  CLIT Controller IDE
  Vibe with CLIT Controller
  → http://localhost:8787
  API docs → http://localhost:8787/docs

INFO:     Uvicorn running on http://127.0.0.1:8787 ...
  VITE v5.x  ready in NNN ms
  ➜  Local:   http://localhost:5180/
```

### Health check

```bash
curl http://localhost:8787/api/health
```

Returns (see [app.py](../backend/agentflow/app.py)):

```json
{"ok": true, "app": "CLIT Controller IDE", "fullName": "Command Line Interface Terminal Controller", "tagline": "Vibe with CLIT Controller", "version": "0.1.0"}
```

You can also open http://localhost:8787/docs to browse the API interactively.

## First-run problems

- **No workspace selected (HTTP 409).** On a clean install no workspace is
  chosen yet, so workspace-scoped API calls return
  `409 No workspace selected. Set one on the Projects page.`
  (see [routes_projects.py](../backend/agentflow/api/routes_projects.py)), and
  the terminal prints `No workspace selected. Pick one in Explorer.` Pick a
  workspace in the UI first; selecting one materializes its
  `<workspace>/.agentflow/` state files.
- **Provider CLI not installed.** The app orchestrates external coding-agent
  CLIs (`claude`, `codex`, `agy`) as subprocesses. If a CLI is not on `PATH`,
  the terminal for that provider fails to launch — install the CLI you intend to
  use. The app itself starts fine without them.
- **Port already in use.** `./scripts/dev.sh` frees ports 8787 and 5180 before
  starting (SIGTERM, escalating to SIGKILL), so a stale backend or Vite server is
  cleaned up automatically. To use a different backend port:
  `AGENTFLOW_PORT=9000 ./scripts/dev.sh`.
- **npm cache permission error.** Handled automatically by `install.sh` (see the
  isolated-cache retry under [Setup](#2-setup-one-time)).
- **`.venv missing`.** If `./scripts/dev.sh` exits with
  `error: .venv missing — run ./scripts/install.sh first`, run step 2.

## Optional: production / single-port build

To serve the frontend from the backend on a single port (8787), build the
frontend once (`tsc && vite build` → `frontend/dist`), then run the backend:

```bash
# from repository root
make build
.venv/bin/python -m agentflow
```

With `frontend/dist` present, http://localhost:8787 serves the built app
directly (see [app.py](../backend/agentflow/app.py)). The dev server on 5180 is
not needed in this mode.

## Stop and clean

- **Stop `make dev` / `./scripts/dev.sh`:** press `Ctrl-C` in the terminal. The
  script's cleanup trap stops the backend (which reaps its PTY terminal
  children) and frees port 5180.
- **Remove caches and build artifacts:**

  ```bash
  # from repository root
  make clean
  ```

  This removes `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `frontend/dist`,
  and backend `__pycache__` directories (see [Makefile](../Makefile)). It does
  not delete `.venv`, `node_modules`, or your on-disk app state under
  `~/.agentflow/` or `<workspace>/.agentflow/`.

## Next steps

- One command surface for everything else: `make setup | dev | format | lint |
  typecheck | test | build | verify | clean` (see [Makefile](../Makefile)).
- Run the full local verification (mirrors CI): `make verify`.
- Runtime model, state files, and recovery: [OPERATIONS.md](OPERATIONS.md).
- Product pillars and interaction model: [PILLARS.md](PILLARS.md).
