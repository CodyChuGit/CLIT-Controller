# Configuration

Configuration is split between global state in `~/.agentflow/config.json` and a
workspace mirror in `<workspace>/.agentflow/config.json`.

## Environment Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENTFLOW_PORT` | `8787` | Backend port. |
| `SHELL` | login shell, fallback `/bin/bash` | Shell used for PTY terminal sessions. |
| `HEADROOM_SAVINGS_PROFILE` | `agent-90` | Used by helper scripts; managed app settings are preferred. |

The backend strips `PORT` and `AGENTFLOW_PORT` from child process env so preview
servers do not bind over the CLIT Controller backend.

## Routing Defaults

Default routing:

```json
{
  "orchestrator": "claude",
  "pm": "codex",
  "engineer": "claude",
  "qa": "antigravity"
}
```

Settings can change routing. The UI excludes Antigravity from the controller
role, and the backend migrates old Antigravity/Gemini controller configs to
Claude.

## Command Templates

Command templates are argv templates parsed with `shlex`. `{prompt}` is passed
as one argument. `{model}` expands to provider-specific model flags or
disappears when unset.

Defaults:

| Provider | Template |
| --- | --- |
| `codex` | `codex exec --skip-git-repo-check --sandbox workspace-write {model} {prompt}` |
| `claude` | `claude -p --permission-mode acceptEdits --verbose --output-format stream-json {model} {prompt}` |
| `antigravity` | `agy --sandbox {model} -p {prompt}` |

Claude uses `stream-json`; `stream_normalizer.py` converts streamed JSONL back
to readable text before downstream consumers see it.

## Models

`models` maps provider id to the selected model. Empty or missing means the CLI
default. Model options are shown on the Agents page and refreshed where a CLI
exposes a model command.

## Headroom

Headroom is the input-side token compression proxy.

Default settings:

```json
{
  "enabled": true,
  "proxyUrl": "http://127.0.0.1:8799",
  "savingsProfile": "agent-90"
}
```

When enabled and installed, CLIT Controller starts a managed Headroom proxy.
When the proxy is reachable:

- `claude` receives `ANTHROPIC_BASE_URL`
- `codex` receives `OPENAI_BASE_URL`

Antigravity is not routed through Headroom. If Headroom is unavailable, agents
run directly.

## Ponytail

Ponytail is output-side prompt discipline. Levels:

- `off`
- `lite`
- `full`
- `ultra`

Default: `full`.

## Workspace Selection

The current workspace is stored globally. Workspace-specific state is written
under `<workspace>/.agentflow/`. Routes that operate on files, tasks, queue,
preview, terminals, or events require a selected workspace.

## Provider Resolution

Provider probing checks normal `PATH` plus common user bin directories:

- `~/.local/bin`
- `~/bin`

This is important for Antigravity, whose installer commonly places `agy` in
`~/.local/bin`.
