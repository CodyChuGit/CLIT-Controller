# Troubleshooting

Failure modes you can actually hit running CLIT Controller IDE / AgentComposer locally, with how to diagnose and fix each. Every command here is from this repo's scripts, [Makefile](../Makefile), tests, and runtime code.

This guide assumes you have read the runtime model in [OPERATIONS.md](OPERATIONS.md) and the setup steps in [GETTING_STARTED.md](GETTING_STARTED.md). For security/origin behavior see [SECURITY.md](SECURITY.md); for the overall layout see [ARCHITECTURE.md](ARCHITECTURE.md).

Each entry uses: **Symptom / Likely cause / Diagnosis / Resolution / Prevention**.

---

## 1. Python version too old (need 3.11+)

**Symptom.** `./scripts/install.sh` exits with:

```
error: Python 3.11+ not found. Install it (e.g. brew install python@3.12) and re-run.
```

**Likely cause.** `install.sh` searches `PYTHON`, then `python3.13 python3.12 python3.11 python3`, and accepts the first interpreter whose `sys.version_info >= (3, 11)`. If your only `python3` on `PATH` is older (e.g. a system 3.9), none of the candidates qualify. The project requires `>=3.11` (see `requires-python` in [backend/pyproject.toml](../pyproject.toml)).

**Diagnosis.**

```bash
python3 --version
for c in python3.13 python3.12 python3.11; do command -v "$c" && "$c" --version; done
```

**Resolution.** Install a 3.11+ interpreter and re-run setup. If it is installed but not the default `python3`, point setup at it explicitly:

```bash
brew install python@3.12
PYTHON=python3.12 ./scripts/install.sh
```

**Prevention.** Keep a 3.11+ interpreter on `PATH`. The venv created at `.venv` pins the chosen version, so once it exists the system `python3` no longer matters for running the app.

---

## 2. `.venv` missing

**Symptom.** `./scripts/dev.sh` exits immediately with:

```
error: .venv missing — run ./scripts/install.sh first
```

`dev.sh` guards on `[ ! -x .venv/bin/python ]` before doing anything else. Also seen as `make dev` / `make test` failing because `PY := .venv/bin/python` does not exist.

**Likely cause.** Setup was never run, or `.venv` was deleted (e.g. by `make clean`-adjacent cleanup) or was created incompletely.

**Diagnosis.**

```bash
ls -l .venv/bin/python
```

**Resolution.**

```bash
make setup      # or: ./scripts/install.sh
```

This creates `.venv`, installs the backend editable with dev extras (`pip install -e ".[dev]"`), and installs frontend deps.

**Prevention.** Run `make setup` once per clone. Do not delete `.venv` between runs.

---

## 3. npm install fails (EACCES / EEXIST cache errors)

**Symptom.** During `./scripts/install.sh` (or `make setup`) the frontend install fails with permission or lock errors under `~/.npm`, e.g. `EACCES: permission denied` or `EEXIST`. `install.sh` then prints:

```
==> npm install failed (often a ~/.npm permissions issue) — retrying with an isolated cache
```

**Likely cause.** A `~/.npm` cache owned by root or otherwise unwritable (common after a `sudo npm` somewhere in the past).

**Diagnosis.**

```bash
ls -ld ~/.npm
npm config get cache
```

**Resolution.** `install.sh` already retries automatically with an isolated cache:

```bash
(cd frontend && npm install --no-fund --no-audit --cache "${TMPDIR:-/tmp}/agentflow-npm-cache")
```

If you are running npm by hand outside the script, use the same isolated cache. The provider install commands for the global CLIs follow the same pattern, e.g. `npm install -g @anthropic-ai/claude-code --no-fund --no-audit --cache /tmp/agentflow-npm-cache` (see [provider_probe.py](../backend/agentflow/provider_probe.py)).

**Prevention.** Avoid `sudo npm`. If `~/.npm` is already root-owned, either `sudo chown -R "$(whoami)" ~/.npm` or keep using the isolated cache.

---

## 4. Port 8787 or 5180 already in use

**Symptom.** Backend fails to bind `127.0.0.1:8787`, or the Vite dev server can't take `5180`. Or worse: the app loads but serves *old* behavior because a stale `python -m agentflow` from a previous run is still holding `:8787`.

**Likely cause.** A previous backend or Vite dev server did not exit (crash, detached process, closed terminal without Ctrl-C). The stale backend keeps serving its old in-memory code.

**Diagnosis.**

```bash
lsof -nP -tiTCP:8787 -sTCP:LISTEN
lsof -nP -tiTCP:5180 -sTCP:LISTEN
```

**Resolution.** `./scripts/dev.sh` frees both ports before (re)starting — its `free_port()` helper sends `SIGTERM` (so a live backend runs its shutdown hook and reaps PTY children), waits up to ~5s, then escalates to `SIGKILL`. So the normal fix is simply to re-run:

```bash
./scripts/dev.sh
```

To free a wedged port manually:

```bash
lsof -ti tcp:8787 | xargs kill -9    # last-resort: skips graceful child reaping
lsof -ti tcp:5180 | xargs kill -9
```

To change the backend port instead of freeing it, set `AGENTFLOW_PORT` (note the Vite proxy in [frontend/vite.config.ts](../frontend/vite.config.ts) targets `http://127.0.0.1:8787`, so a non-default port also needs the proxy target updated for dev mode).

**Prevention.** Stop the app with Ctrl-C in the `dev.sh` terminal — its `trap cleanup EXIT INT TERM` kills the backend gracefully (children reaped) and frees `:5180`. The backend also runs `sweep_orphaned_sessions()` on startup to reap leaked PTY children of a previously SIGKILLed backend.

---

## 5. "No workspace selected" (409)

**Symptom.** API calls return HTTP 409 with:

```
No workspace selected. Set one on the Projects page.
```

In a live terminal you instead see (yellow ANSI): `No workspace selected. Pick one in Explorer.`

**Likely cause.** No current workspace is set in the global config. Workspace-scoped routes require one (raised in [routes_projects.py](../backend/agentflow/api/routes_projects.py); the terminal WebSocket short-circuits with the message above, see [routes_terminals.py](../backend/agentflow/api/routes_terminals.py)).

**Diagnosis.**

```bash
cat ~/.agentflow/config.json   # look for the current workspace path
```

**Resolution.** Open the Projects page in the UI and pick (or add) a workspace directory. State for that workspace lives under `<workspace>/.agentflow/`.

**Prevention.** Select a workspace before driving tasks, terminals, or project file routes. A first-run install has no workspace until you set one.

---

## 6. Provider CLI not installed (claude / codex / agy / gh)

**Symptom.** A terminal or task that launches an agent prints `command not found`, or the Agents page shows a provider as not installed.

**Likely cause.** The provider's CLI is not on `PATH`. The backend detects CLIs by probing `executableNames` (e.g. `claude`, `codex`, `agy`/`antigravity`, `gh`, `git`, `ollama`) — see [provider_probe.py](../backend/agentflow/provider_probe.py).

**Diagnosis.** On the Agents page, hit **Check** for the provider. By hand:

```bash
command -v claude codex agy gh git
```

**Resolution.** Install the missing CLI using the provider's documented command (also surfaced on the Agents page). Examples straight from the probe metadata:

```bash
npm install -g @anthropic-ai/claude-code --no-fund --no-audit --cache /tmp/agentflow-npm-cache   # claude
npm install -g @openai/codex --no-fund --no-audit --cache /tmp/agentflow-npm-cache               # codex
curl -fsSL https://antigravity.google/cli/install.sh | bash                                       # agy → ~/.local/bin
brew install gh                                                                                   # gh
```

After installing `agy`, ensure `~/.local/bin` is on `PATH`. Then re-run **Check**.

**Prevention.** Install the CLIs you intend to orchestrate before assigning them to tasks; log in where required (`gh auth login`, `codex login`, run `claude` / `agy` once to authenticate).

---

## 7. Headroom proxy not running (token-saving optimization absent)

**Symptom.** You enabled Headroom but agents don't appear to route through it; the Headroom status reports `reachable: false`. Agents still run — just directly against the provider.

**Likely cause.** This is **by design**: the Headroom integration is **fail-open**. If Headroom is disabled, the proxy is unreachable, or the reachability probe times out, the backend runs the agent directly with no proxy env. See [headroom_service.py](../backend/agentflow/headroom_service.py). It is off by default (`headroom.enabled = false`).

**Diagnosis.** The service does a bounded TCP probe (300 ms, cached 5 s) against the configured `proxyUrl` (default `http://127.0.0.1:8799`).

```bash
lsof -nP -tiTCP:8799 -sTCP:LISTEN     # is the proxy listening?
cat ~/.agentflow/config.json          # check "headroom": {"enabled": ...}
```

**Resolution.** Start the proxy and enable it:

```bash
./scripts/headroom.sh                 # binds :8799 — NOT :8787
```

Then turn it on in Settings (or set `"headroom": {"enabled": true}` in `~/.agentflow/config.json`). Once enabled **and** reachable, the backend sets `ANTHROPIC_BASE_URL` for `claude` and `OPENAI_BASE_URL` (+`/v1`) for `codex`.

> Do **not** point Headroom at `:8787` — that is the AgentComposer backend port (and also Headroom's own default), which would collide. `headroom.sh` uses `:8799` deliberately.

**Prevention.** Treat Headroom as optional. If you depend on the savings, start `headroom.sh` before launching agents and confirm `reachable: true` in the Headroom status.

---

## 8. Live terminal session stuck or orphaned

**Symptom.** A terminal tab is frozen, a CLI agent won't exit, or after a backend crash you find leftover `agy`/`codex`/`claude` processes still running.

**Likely cause.** A TUI ignoring the pty EOF, or a backend that was SIGKILLed before its shutdown hook could reap PTY children. Each session is one PTY + child process group (see [terminal_service.py](../backend/agentflow/terminal_service.py)).

**Diagnosis.**

```bash
ls ~/.agentflow/run/terminals/        # *.session pidfiles record live PTY shells
ps -o pid,tty,command -p <pid>        # PTY shells we spawned show tty "??"
```

**Resolution.**
- From the UI: use the terminal **kill** action. It posts to `POST /api/terminals/{provider}/kill`, which calls `TERMINALS.kill(...)` and terminates the session's process group (`terminate()` sends `SIGTERM`, then `SIGKILL` as a backstop). The WebSocket also accepts `{"type": "kill"}`.
- After a crash: just restart the backend. On startup it calls `sweep_orphaned_sessions()`, which SIGKILLs recorded process-groups that are still detached shells we plausibly spawned (no controlling tty plus matching shell name, guarding against pid reuse).

**Prevention.** Stop the app with Ctrl-C so the shutdown hook reaps children cleanly, rather than killing the backend with `kill -9`.

---

## 9. Frontend can't reach the backend

**Symptom.** The UI loads on `http://localhost:5180` but API calls fail (network errors, 502/504, or hanging requests). Or a browser tab on some other origin gets `403 cross-origin request rejected`.

**Likely cause.**
- The backend isn't running, so the Vite dev proxy has nothing to forward to. In dev mode the frontend talks to the backend only through Vite's proxy: `/api → http://127.0.0.1:8787` with `ws: true` (so terminal WebSockets proxy too). See [frontend/vite.config.ts](../frontend/vite.config.ts).
- Or you're hitting the API from an origin that isn't allowlisted. The app only accepts its own local origins — `localhost`/`127.0.0.1` on `:5180` and `:8787` — enforced for CORS, the CSRF `OriginGuardMiddleware`, and the WebSocket origin check via [origins.py](../backend/agentflow/origins.py). A cross-origin mutating request is rejected with 403.

**Diagnosis.**

```bash
lsof -nP -tiTCP:8787 -sTCP:LISTEN     # backend listening?
curl -sS http://127.0.0.1:8787/api/health   # or another known route; expect a response
```

**Resolution.** Start the backend (or just run `./scripts/dev.sh`, which starts both). Use `http://localhost:5180` (dev) or `http://localhost:8787` (single-port built mode) — not a LAN IP or other host, which won't pass the origin allowlist.

**Prevention.** Run both processes via `dev.sh`. Don't open the UI on an origin outside the allowlist; see [SECURITY.md](SECURITY.md) for why loopback-only origins are enforced.

---

## 10. Build / typecheck / lint failures

**Symptom.** `make build`, `make typecheck`, or `make lint` fails — `tsc` type errors, `vite build` errors, `mypy` errors, or `ruff` findings.

**Likely cause.** Real type/lint regressions, or stale frontend deps after a dependency change.

**Diagnosis.** Run the individual targets to isolate the failing side:

```bash
make typecheck      # mypy (backend) + tsc (frontend)
make lint           # ruff check (backend) + eslint (frontend)
make build          # tsc && vite build → frontend/dist
```

**Resolution.** Fix the reported errors. If frontend errors look like missing/stale modules after pulling, reinstall deps:

```bash
(cd frontend && npm install --no-fund --no-audit --cache "${TMPDIR:-/tmp}/agentflow-npm-cache")
```

Auto-fixable formatting issues: `make format`.

**Prevention.** Run `make verify` before pushing — it mirrors CI (`format-check lint typecheck test build`). See [ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md).

---

## 11. Stale pytest / `__pycache__` giving wrong tracebacks

**Symptom.** Backend tests fail (or pass) against code you've already changed: tracebacks point at line numbers that no longer exist, a deleted/renamed module still resolves, or `make test` behaves inconsistently between runs.

**Likely cause.** Stale `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, or `__pycache__` directories from a previous layout.

**Diagnosis.**

```bash
find backend -name __pycache__ -type d | head
ls .pytest_cache .mypy_cache .ruff_cache 2>/dev/null
```

**Resolution.** Clear the caches, then re-run:

```bash
make clean          # removes .pytest_cache .mypy_cache .ruff_cache frontend/dist + backend __pycache__
.venv/bin/python -m pytest backend/tests
```

**Prevention.** Run `make clean` after large refactors or branch switches that move/rename modules.

---

## Quick reference

| You see | Go to |
| --- | --- |
| `Python 3.11+ not found` | [§1](#1-python-version-too-old-need-311) |
| `.venv missing` | [§2](#2-venv-missing) |
| npm EACCES / EEXIST | [§3](#3-npm-install-fails-eacces--eexist-cache-errors) |
| Port already in use / stale backend | [§4](#4-port-8787-or-5180-already-in-use) |
| `No workspace selected` (409) | [§5](#5-no-workspace-selected-409) |
| `command not found` for an agent | [§6](#6-provider-cli-not-installed-claude--codex--agy--gh) |
| Headroom `reachable: false` | [§7](#7-headroom-proxy-not-running-token-saving-optimization-absent) |
| Terminal frozen / orphan processes | [§8](#8-live-terminal-session-stuck-or-orphaned) |
| API errors / `403 cross-origin` | [§9](#9-frontend-cant-reach-the-backend) |
| `tsc` / `vite` / `mypy` / `ruff` fails | [§10](#10-build--typecheck--lint-failures) |
| Wrong/stale tracebacks | [§11](#11-stale-pytest--__pycache__-giving-wrong-tracebacks) |
