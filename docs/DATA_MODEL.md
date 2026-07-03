# Data Model

CLIT Controller uses JSON files, markdown artifacts, and run logs. There is no
database.

## Global State

Global state lives under `~/.agentflow/`.

| Path | Purpose |
| --- | --- |
| `config.json` | Current workspace, routing defaults, command templates, model selections, Headroom settings, Ponytail level. |
| `providers.json` | Cached provider probe/install status. |
| `usage.json` | Provider usage counters and manual health when no workspace is active. |
| `run/terminals/*.session` | PTY session pidfiles used for orphan cleanup. |

## Workspace State

Workspace state lives under `<workspace>/.agentflow/`.

| Path | Purpose |
| --- | --- |
| `config.json` | Workspace routing/settings mirror. |
| `chat.json` | Controller and provider chat history. |
| `events.json` | Durable structural event ledger. |
| `runs.json` | Durable run ledger. |
| `approvals.json` | Durable approvals. |
| `queue.json` | Execution queue. |
| `usage.json` | Workspace usage counters and provider health. |
| `logs.json` | Global visible log entries. |
| `tasks/<task_id>/` | Task artifacts, task metadata, prompt/output logs. |

## Task Folder

Each task has a folder:

```text
<workspace>/.agentflow/tasks/<task_id>/
  task.json
  00_USER_GOAL.md
  01_CODEX_SPEC.md
  02_CODEX_IMPLEMENTATION_PLAN.md
  03_CLAUDE_PROMPT.md
  04_CLAUDE_IMPLEMENTATION_SUMMARY.md
  05_QA_RESULTS.md
  06_BUGS_FOR_CLAUDE.md
  07_CODEX_FINAL_REVIEW.md
  ROUTING_DECISIONS.md
  logs/
```

The `gemini_qa` step id is retained for compatibility with existing task files,
but the QA role routes to `antigravity` by default.

## Important JSON Shapes

### `task.json`

Stores:

- id, title, goal, createdAt, status
- per-step state
- `fullSequence`
- task events
- orchestrated flag
- controller consult count
- final orchestrator verdict when complete

### `queue.json`

Stores:

- queue items
- task id
- step
- label
- provider
- status
- attempt
- provider override
- run id
- timestamps
- note

The dispatcher enforces one active item per provider and preserves intra-task
ordering.

### `events.json`

Stores durable structural events, not every text chunk. Text chunks stream
through the live event bus and are written into run logs.

Common event types:

- `run.started`
- `run.finished`
- `queue.*`
- `approval.*`
- `task.*`
- `controller.result_invalid`
- `controller.legacy_directives`
- `controller.turn_completed`

### `runs.json`

Stores run metadata:

- id
- command preview
- cwd
- provider
- task id
- step
- status
- pid
- timestamps
- duration
- exit code
- prompt/log paths
- stdout/stderr tails
- truncation flag
- failure kind

### `approvals.json`

Stores approval records:

- id
- action
- kind
- source
- provider
- task id
- reason
- status
- timestamps
- resolver

Approvals survive restart and can be listed through `/api/approvals`.

## Atomic Writes And Migrations

JSON writes use temporary files plus rename.

Config loaders migrate old provider names forward:

- `gemini` -> `antigravity`
- old Antigravity-as-controller configs -> `claude`
- stale command templates -> current defaults

## Recovery

`state_store.recover_workspace` runs on backend startup and workspace selection.
It settles stale running state in:

- run ledger
- queue
- task steps

`terminal_service.sweep_orphaned_sessions` uses terminal pidfiles to kill
abandoned PTY process groups after a backend crash.
