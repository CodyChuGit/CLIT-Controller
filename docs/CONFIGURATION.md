# Configuration

CLIT Controller IDE / AgentComposer is a **local-first, single-user** tool. Almost
all runtime configuration lives in **JSON files** under `~/.agentflow/` (global) and
`<workspace>/.agentflow/` (per-project), not in environment variables. There is no
database and no `.env` is required to run — the few real env knobs are listed below.

For where these files live on disk see [paths.py](../backend/agentflow/paths.py); for
the operational picture see [docs/OPERATIONS.md](OPERATIONS.md), and for the
no-auth / loopback-only posture see [docs/SECURITY.md](SECURITY.md).

## Environment variables

| Variable | Required | Default | Scope | Sensitive | Description |
|---|---|---|---|---|---|
| `AGENTFLOW_PORT` | No | `8787` | Backend (process) | No | TCP port the backend binds on `127.0.0.1`. In single-port mode it also serves the built frontend. Read in [`__main__.py`](../backend/agentflow/__main__.py); also honored by [`scripts/app-mode.sh`](../scripts/app-mode.sh). |
| `SHELL` | No | login `$SHELL`, then `/bin/bash` | Backend (PTY child) | No | Shell launched for live PTY terminal sessions. Read in [`terminal_service.py`](../backend/agentflow/terminal_service.py) (`_shell()`). |
| `HEADROOM_PROXY_PORT` | No | `8799` | `scripts/headroom.sh` only | No | Port the Headroom proxy listens on. Used only by the helper script, not by the backend. See [`scripts/headroom.sh`](../scripts/headroom.sh). |
| `HEADROOM_SAVINGS_PROFILE` | No | `agent-90` | `scripts/headroom.sh` only | No | Compression/accuracy profile passed to `headroom agent-savings`. Script-only. |
| `HEADROOM_BIN` | No | `$HOME/.local/bin/headroom` | `scripts/headroom.sh` only | No | Path to the `headroom` binary. Script-only. |
| `import.meta.env.PROD` | n/a (auto) | set by Vite | Frontend (build-time) | No | Vite built-in build flag. Gates service-worker registration to production builds. Read in [`main.tsx`](../frontend/src/main.tsx); typed via [`vite-env.d.ts`](../frontend/src/vite-env.d.ts). Not a user-settable env var. |

### Notes and non-knobs

- **`PORT` is filtered, never read.** The backend itself does not read `PORT`. It
  *strips* both `PORT` and `AGENTFLOW_PORT` from the environment of every agent
  subprocess it spawns, so a child dev server can't honor our `PORT`/`AGENTFLOW_PORT`
  and bind on top of the backend. See `start()` in
  [`process_runner.py`](../backend/agentflow/process_runner.py)
  (`child_env = {k: v ... if k not in ("PORT", "AGENTFLOW_PORT")}`).
- **PTY child env defaults (not user knobs).** The terminal child env always sets
  `TERM=xterm-256color` and `setdefault`s `LANG=en_US.UTF-8` and `COLORTERM=truecolor`,
  and prepends provider-CLI bin dirs to `PATH`. See `_child_env()` in
  [`terminal_service.py`](../backend/agentflow/terminal_service.py). These are emitted, not
  configured.
- **`scripts/dev.sh` hard-codes ports.** The dev runner pins `BACKEND_PORT=8787` and
  `FRONTEND_PORT=5180` as literals (not env-driven). See
  [`scripts/dev.sh`](../scripts/dev.sh). The Vite dev server port (`5180`) and its `/api`
  proxy target (`http://127.0.0.1:8787`) are likewise hard-coded in
  [`frontend/vite.config.ts`](../frontend/vite.config.ts).
- **No `VITE_*` runtime variables.** The frontend reads no custom Vite env vars; only
  the built-in `import.meta.env.PROD` is used.
- **Provider API keys are intentionally absent.** The agent CLIs (`claude`, `codex`,
  `agy`) authenticate through their own config/keychain. This app never reads provider
  keys and none belong in the environment or `.env`. See
  [docs/SECURITY.md](SECURITY.md).

### `.env.example` parity

[`.env.example`](../.env.example) documents `AGENTFLOW_PORT` and `SHELL`. The
Headroom variables (`HEADROOM_PROXY_PORT`, `HEADROOM_SAVINGS_PROFILE`,
`HEADROOM_BIN`) are read **only** inside [`scripts/headroom.sh`](../scripts/headroom.sh)
(which documents them in its own header and usage) and are not part of the backend's
runtime environment, so their omission from `.env.example` is intentional rather than a
gap. No backend-read environment variable is missing from `.env.example`.

## Startup validation

- The backend binds `127.0.0.1` with the resolved `AGENTFLOW_PORT` and prints the URL;
  see [`__main__.py`](../backend/agentflow/__main__.py).
- Configuration is validated **lazily**: `load_global_config()` reads the JSON, falls
  back to defaults for any missing or unparseable file (`read_json` swallows
  `FileNotFoundError`/`JSONDecodeError` and returns the default), and migrates stale
  entries (e.g. Gemini routing → Antigravity, upgraded command templates). See
  [`config.py`](../backend/agentflow/config.py).
- `set_workspace()` **refuses dangerous roots**: it rejects the filesystem root (`/`,
  detected via `workspace == workspace.parent`) and your home directory (`$HOME`), since
  the read/write/git/command surfaces are confined to the chosen workspace. It also
  requires the path to be an existing directory (`ensure_workspace` raises
  `FileNotFoundError` otherwise). See `set_workspace` / `ensure_workspace` in
  [`config.py`](../backend/agentflow/config.py).

## File-based configuration

### Global — `~/.agentflow/config.json`

Located via [`paths.py`](../backend/agentflow/paths.py) (`global_config_file()` →
`~/.agentflow/config.json`). Loaded and defaulted by `load_global_config()` in
[`config.py`](../backend/agentflow/config.py). All writes are atomic (tmp file + rename).

| Key | Type | Default | Read by | Description |
|---|---|---|---|---|
| `currentWorkspace` | string \| null | `null` | `get_current_workspace()` | Absolute path to the active workspace. Returns `None` if unset or no longer a directory. Set by `set_workspace()`. |
| `routing` | object | `{orchestrator: antigravity, pm: codex, engineer: claude, qa: antigravity}` (`DEFAULT_ROUTING`) | `update_settings`, `get_workspace_routing` | Maps each agent role → provider id. Legacy `gemini` values are migrated to `antigravity` on load (`_migrate_gemini`). Also mirrored into the workspace config when updated. |
| `commandTemplates` | object | `DEFAULT_COMMAND_TEMPLATES` (per provider, see below) | `get_command_templates()` | Per-provider argv template strings for `codex` / `claude` / `antigravity`. `{prompt}` and `{model}` placeholders are expanded (shlex-parsed argv, never shell-interpolated). Stale/previous defaults are auto-upgraded; a `gemini` template is dropped. |
| `models` | object | `{}` | `get_models()` | Provider id → model name (`""`/absent = the CLI's own default). Stored trimmed; blank values are dropped on save. |
| `headroom` | object | `{}` (merged with `_DEFAULTS`) | `headroom_service.settings()` | Optional Headroom token-saving proxy (Pillar 1). Keys: `enabled` (bool, default `false`), `proxyUrl` (default `http://127.0.0.1:8799`), `savingsProfile` (default `agent-90`). Off by default; see below. |

Default command templates (from `DEFAULT_COMMAND_TEMPLATES` in
[`config.py`](../backend/agentflow/config.py)):

| Provider | Template |
|---|---|
| `codex` | `codex exec --skip-git-repo-check --sandbox workspace-write {model} {prompt}` |
| `claude` | `claude -p --permission-mode acceptEdits {model} {prompt}` |
| `antigravity` | `agy --sandbox {model} -p {prompt}` |

#### Headroom section (Pillar 1)

The `headroom` object in the global config is merged over defaults in
`headroom_service.settings()` (see
[`headroom_service.py`](../backend/agentflow/headroom_service.py)):

| Key | Default | Description |
|---|---|---|
| `enabled` | `false` | When `true` *and* the proxy is reachable, `claude`/`codex` agent subprocesses get `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL` (with a `/v1` suffix for OpenAI) pointing at the proxy. |
| `proxyUrl` | `http://127.0.0.1:8799` | Proxy base URL. Deliberately not `:8787` (the backend port, which is also Headroom's own default — they would collide). |
| `savingsProfile` | `agent-90` | Reported in status only; the actual compression profile is applied when the proxy is started by [`scripts/headroom.sh`](../scripts/headroom.sh). |

Behavior is **fail-open**: if disabled, the provider is unsupported (`antigravity` is
excluded by design), or the proxy fails a bounded 300 ms TCP reachability probe, the
agent runs directly against its provider. See [docs/PILLARS.md](PILLARS.md) Pillar 1.

### Other global state files

These live under `~/.agentflow/` (per [`paths.py`](../backend/agentflow/paths.py)) and are
not user-edited config but are part of global state:

- `providers.json` — provider detection cache (`providers_cache_file()`).
- `bin/` — generated login helper scripts (`login_scripts_dir()`).
- `run/terminals/` — per-session pidfiles used to reap orphaned PTY sessions on the next
  startup (`terminals_run_dir()`).

### Per-workspace — `<workspace>/.agentflow/config.json`

Created by `ensure_workspace()`; located via `workspace_config_file()` in
[`paths.py`](../backend/agentflow/paths.py). Read/written with `read_json` /
`get_workspace_setting` / `set_workspace_setting` and `get_workspace_routing` in
[`config.py`](../backend/agentflow/config.py).

| Key | Type | Default | Description |
|---|---|---|---|
| `workspacePath` | string | the workspace path | Absolute path recorded on creation; kept in sync by `set_workspace_setting` / routing updates. |
| `routing` | object | copied from the global `routing` at creation | Per-workspace role→provider overrides. Merged over `DEFAULT_ROUTING` and Gemini-migrated by `get_workspace_routing`. Re-synced from global when global routing is updated while this workspace is active. |

`ensure_workspace()` also materializes the rest of the per-workspace layout on first
selection: a self-ignoring `.agentflow/.gitignore` (`*`), the `tasks/` directory
(`tasks_dir()`), and `usage.json` (via `usage_service.ensure_usage`). Other
per-workspace files (`events.json`, `runs.json`, `approvals.json`, `queue.json`,
`chat.json`) are created on demand by their respective services. Arbitrary
per-workspace settings can also be stored via `set_workspace_setting()` /
`get_workspace_setting()`.

## See also

- [docs/PILLARS.md](PILLARS.md) — the five product pillars and interaction model.
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — system design and module map.
- [docs/OPERATIONS.md](OPERATIONS.md) — running, ports, and state files.
- [docs/SECURITY.md](SECURITY.md) — loopback-only, no-auth, secret handling.
- [docs/ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md) — coding conventions.
