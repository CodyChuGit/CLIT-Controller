# Architecture Contracts

This document defines the backend shape needed to make traffic control predictable,
durable, and extensible while preserving the current app structure.

## Component Boundaries

| Component | Owns | Should not own |
|---|---|---|
| API routes | Request validation, HTTP status mapping, response DTOs | Business rules |
| Workspace service | Workspace selection, `.agentflow/` layout, safe path resolution | Agent routing |
| Provider registry | Provider definitions, capabilities, command template rendering | Queue decisions |
| Controller service | Prompt construction, decision parsing, consult loop | Raw subprocess details |
| Task service | Task metadata, markdown artifacts, task state transitions | Provider installation |
| Queue service | Queue ordering, dispatch eligibility, approval holds | Prompt generation details |
| Execution service | Durable run records, process lifecycle, streaming output | Controller policy |
| Policy service | Command classification, approval requirements, denials | Process execution |
| Usage service | Approximate and live provider usage | Routing implementation details |
| Event service | Append-only events, subscriptions, projections | Domain-specific decisions |

The current modules can evolve into these boundaries incrementally. The important
change is making state transitions and policy decisions explicit instead of letting
them live inside route handlers or completion callbacks.

## Durable State Model

Keep markdown artifacts on disk. Add a durable machine state layer under
`<workspace>/.agentflow/`.

Recommended layout:

```text
.agentflow/
  config.json
  usage.json
  state.db
  tasks/
    <task-id>/
      task.json
      logs/
      00_USER_GOAL.md
      ...
```

`state.db` should hold queue items, run records, events, approvals, provider snapshots,
and traffic-control decisions. `task.json` may remain as a readable task snapshot, but
the backend should treat the durable event/run store as authoritative for recovery.

If SQLite is deferred, the same contracts still apply to JSON files:

- Atomic writes.
- File locks around queue/task/run mutations.
- Schema version on every persisted document.
- Recovery migration on load.

## Core Entities

### Task

Required fields:

- `id`
- `workspacePath`
- `title`
- `goal`
- `status`
- `createdAt`
- `updatedAt`
- `orchestrated`
- `consultCount`
- `finalVerdict`
- `steps`
- `artifacts`

Valid statuses:

```text
new -> in_progress -> done
new -> in_progress -> needs_user
new -> in_progress -> failed
new -> in_progress -> cancelled
needs_user -> in_progress
failed -> in_progress
```

### Step

Required fields:

- `id`
- `taskId`
- `kind`
- `role`
- `provider`
- `status`
- `runId`
- `reads`
- `writes`
- `attempt`
- `dependsOn`

Valid statuses:

```text
idle
queued
awaiting_approval
running
succeeded
skipped
blocked
failed
cancelled
provider_missing
policy_denied
```

### Queue Item

Required fields:

- `id`
- `taskId`
- `step`
- `provider`
- `source`
- `status`
- `enqueuedAt`
- `startedAt`
- `finishedAt`
- `runId`
- `approvalId`
- `note`

Rules:

- A task cannot run later queued items while an earlier active item is blocked,
  awaiting approval, or running.
- A provider cannot run two queue items at once.
- Active duplicate `(taskId, step)` items are rejected.
- Failed queue items block later queued items for that task until approval, retry,
  skip, or reroute.

### Run

Required fields:

- `id`
- `workspacePath`
- `argv`
- `cwd`
- `provider`
- `taskId`
- `step`
- `status`
- `pid`
- `startedAt`
- `endedAt`
- `durationMs`
- `exitCode`
- `promptFile`
- `logFile`
- `stdoutTail`
- `stderrTail`
- `outputTruncated`
- `failureKind`

Failure kinds:

```text
provider_missing
auth_required
policy_denied
validation_error
start_error
timeout
exit_nonzero
cancelled
backend_restart
unknown
```

### Event

Every state change should append an event:

- `chat.delta`
- `chat.finished`
- `task.created`
- `task.status_changed`
- `queue.enqueued`
- `queue.changed`
- `queue.approval_required`
- `queue.dispatched`
- `command.started`
- `command.finished`
- `run.started`
- `run.output`
- `run.stderr`
- `run.heartbeat`
- `run.finished`
- `run.cancelled`
- `orchestrator.consult_requested`
- `orchestrator.decision_received`
- `policy.denied`
- `approval.granted`
- `approval.rejected`
- `usage.recorded`

Events are the basis for streaming updates and for rebuilding projections after
restart.

Text-bearing events should include stable ordering and routing fields:

- `id`
- `createdAt`
- `workspacePath`
- `provider`
- `taskId`
- `runId`
- `queueItemId`
- `step`
- `sequence`
- `channel`
- `textDelta`
- `redacted`
- `truncated`

The backend must redact before persisting or broadcasting text events. Frontend
surfaces should render text events from the shared stream rather than each page
polling logs independently.

Text events should be emitted as generated or received. The execution service
must not wait for process exit or complete stdout/stderr capture before emitting
`textDelta` events.

## Provider Adapter Contract

Provider-specific behavior should be behind an adapter interface.

```python
class ProviderAdapter:
    id: str
    display_name: str
    roles: set[str]
    capabilities: set[str]

    def detect(self) -> ProviderState: ...
    def render_command(self, prompt: str, model: str | None, purpose: str) -> list[str]: ...
    def classify_failure(self, run: RunRecord) -> FailureKind: ...
    def parse_usage(self) -> LiveUsage | None: ...
    def install_command(self) -> list[str] | None: ...
    def login_command(self) -> list[str] | None: ...
```

Capabilities should include:

- `chat`
- `plan`
- `implement`
- `qa`
- `review`
- `direct_command`
- `model_selection`
- `usage_probe`
- `installable`
- `speech_to_text`
- `text_to_speech`

This makes Codex, Claude, Antigravity, Ollama, and future local models pluggable
without spreading provider conditionals through task and queue code.

Voice providers may use a narrower adapter contract than coding agents, but they
should still report detection state, command rendering, failure classification,
and local-only capability. The intended first adapters are MLX Parakeet for STT
and `mlx-swift-dots-tts` for TTS.

## Controller Decision Contract

The current fenced-block directives are workable for beta. Full functionality should
parse them into a typed decision list before mutating state.

Decision types:

```text
create_task(title, goal, initial_steps?)
queue_steps(task_ref, steps)
run_command(command, reason?)
mark_done(task_ref, reason)
request_user(task_ref, reason)
retry_step(task_ref, step, reason)
skip_step(task_ref, step, reason)
reroute_step(task_ref, step, provider, reason)
```

Rules:

- Parse all decisions, not just the first task or queue block.
- Validate task references before mutations.
- Validate step IDs against the registry.
- Validate commands through policy before execution.
- Append an `orchestrator.decision_received` event with the parsed decision and
  validation outcome.
- If a response contains no actionable decision during an active consult, mark the
  task `needs_user` with the reasoning tail.

## Display Projection Contract

Controller and task UI should be driven by structured projections rather than raw
agent prose. Each meaningful run, queue item, approval, failure, or task event
should be projectable into three channels:

- `actionData`: strict structured data for backend decisions and UI actions.
- `humanSummary`: concise user-facing summary, ideally five bullets or fewer.
- `displayData`: typed UI model for cards, badges, progress, severity, primary
  action, related artifacts, and raw-detail links.

The right-hand controller tab and Tasks page should consume the same projection.
The controller tab renders compact live cards; the Tasks page renders detailed
cards plus paginated raw detail. Raw JSON, directives, stdout, stderr, logs, and
events remain available for audit, but are not the default display layer.

## Policy Contract

Policy should classify a command or backend action before it reaches execution.

Policy result:

```text
allow
require_approval
deny
```

Inputs:

- command argv
- workspace path
- source: user, orchestrator, queue, route, install helper
- provider
- task id
- traffic control mode

Default classifications:

| Action | Default |
|---|---|
| `git status`, `git diff`, `npm test`, `npm run build` inside workspace | allow |
| Agent step command generated from provider template | allow, subject to provider health |
| `npm install`, `brew install`, provider one-click install | require approval |
| `git push`, `git pull`, `gh pr create`, deploy/publish commands | require approval |
| Shell operators, path traversal, absolute paths outside workspace | deny |
| Recursive destructive filesystem commands | deny unless implemented as explicit UI action |

## API Contract

Preserve existing endpoints where possible. Add versioned or additive responses for
new state.

Important existing frontend consumers:

- `GET /api/projects/current`
- `GET /api/projects/tree`
- `GET /api/projects/git`
- `GET /api/agents`
- `POST /api/agents/check`
- `GET /api/tasks`
- `GET /api/tasks/{id}`
- `POST /api/tasks/{id}/run/{step}`
- `POST /api/tasks/{id}/run-full`
- `GET /api/queue`
- `POST /api/queue/add`
- `POST /api/queue/approve`
- `GET /api/logs`
- `GET /api/chat`
- `POST /api/chat/send`

Add:

- `GET /api/events?cursor=<id>` for polling fallback.
- `GET /api/events/stream` for SSE.
- `POST /api/queue/{item_id}/retry`.
- `POST /api/queue/{item_id}/skip`.
- `POST /api/approvals/{id}/approve`.
- `POST /api/approvals/{id}/reject`.
- `GET /api/runs/{id}`.
- `GET /api/tasks/{id}/timeline`.

## Recovery Contract

On backend startup:

1. Load current workspace.
2. Load durable queue, runs, tasks, and events.
3. For every run marked `running`, check whether the process still exists.
4. If the process exists and belongs to CLITC, reattach where possible.
5. If the process is gone, mark the run `failed` with `failureKind=backend_restart`
   or reconcile from its log file if a terminal marker exists.
6. For every queue item marked `running`, map it to the recovered run status.
7. Block or retry later task items according to policy.
8. Append recovery events.

No queue item should remain `running` forever because an in-memory run record was
lost.
