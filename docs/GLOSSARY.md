# Glossary

Project-specific terms as they are used in **CLIT Controller IDE** / AgentComposer (the
Python package is `agentflow`). These are not generic definitions — each entry reflects
how the term is actually used in this repo, and links to the most relevant doc or source
file. For the product narrative see [PILLARS.md](PILLARS.md) and
[PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md); for the system shape see
[ARCHITECTURE.md](ARCHITECTURE.md).

## Product & roles

### CLIT Controller IDE / Command Line Interface Terminal Controller
The product name. A local-first, single-user, macOS-oriented developer cockpit that
orchestrates CLI coding agents as subprocesses, runs PTY terminals over WebSockets, and
streams agent output live. The Python package is `agentflow`. The login helper scripts
written by [`provider_probe.login_provider`](../backend/agentflow/provider_probe.py) print
the banner "Command Line Interface Terminal Controller". See
[ARCHITECTURE.md](ARCHITECTURE.md).

### Traffic Controller / traffic control
The historical name for the orchestrator role. In docs and code, "controller", "traffic
control", and "orchestrator" all refer to the same thing: the agent that decides what
happens next. The current orchestration-mode labels ("Maximum Quality", "Balanced",
"Budget Saver", "Manual Approval") are called *traffic control modes* in
[`routing_service.py`](../backend/agentflow/routing_service.py). See the note in
[ARCHITECTURE.md](ARCHITECTURE.md).

### controller / orchestrator
The agent in the `orchestrator` routing role (default provider: Antigravity). It reads a
workspace summary plus the chat transcript, then emits **directives** to create tasks,
queue steps, run commands, or hand back to the user — it does not write production code
itself. Driven by [`chat_service.py`](../backend/agentflow/chat_service.py); events from it
use the `orchestrator` channel. See [PILLARS.md](PILLARS.md) (interaction model).

### provider
An external CLI that CLITC detects, installs, and runs. Defined statically in
[`provider_probe.py`](../backend/agentflow/provider_probe.py) (`PROVIDERS`). IDs:
`git`, `gh`, `codex` (OpenAI Codex CLI, role *pm*), `claude` (Claude Code, role *engineer*),
`antigravity` (Google Antigravity CLI, role *controller/qa*), `ollama`, `omlx`. The
**agent providers** are `codex`, `claude`, `antigravity`
(`provider_probe.AGENT_PROVIDER_IDS`). `check_provider` runs each provider's real
`versionCommand`/`statusCommand` and caches the result. See
[CONFIGURATION.md](CONFIGURATION.md).

### agy / antigravity
The Google Antigravity CLI provider (`id: "antigravity"`, the successor to the sunset
Gemini CLI). Its executable is named `agy` (falling back to `antigravity`); the official
installer puts `agy` in `~/.local/bin`, which is why
[`provider_probe.resolve_executable`](../backend/agentflow/provider_probe.py) also searches
`~/.local/bin` and `~/bin` beyond `PATH`. Antigravity is the default `controller`/`qa`
provider and is intentionally **not** routed through the Headroom proxy. See
[CONFIGURATION.md](CONFIGURATION.md).

## Tasks, steps & the workflow

### agent step
A single stage in the standard workflow, defined in
[`workflow.py`](../backend/agentflow/workflow.py) (`STEP_DEFS`). The five step ids and their
routing roles: `codex_spec` (pm — "Write Spec"), `claude_implement` (engineer —
"Implement"), `gemini_qa` (qa — "QA / Test"), `codex_review` (pm — "Final Review"),
`claude_fix` (engineer — "Fix Bugs"). Each step has declared inputs/outputs (`STEP_IO`),
including virtual ones (`@diff`, `@code`, `@folder`). See [DATA_MODEL.md](DATA_MODEL.md).

### task
A unit of work with a title, goal, and per-step state, created by
[`task_service.create_task`](../backend/agentflow/task_service.py). Each task owns a
directory `<workspace>/.agentflow/tasks/<id>/` holding numbered markdown artifacts
(`00_USER_GOAL.md`, `01_CODEX_SPEC.md`, …) plus `task.json` and `ROUTING_DECISIONS.md`.
`task.json` stays authoritative for human reading. See [DATA_MODEL.md](DATA_MODEL.md).

### full sequence
The default automatic chain run for a task:
`codex_spec → claude_implement → gemini_qa → codex_review`
(`workflow.FULL_SEQUENCE`), driven by
[`task_service.run_full_sequence`](../backend/agentflow/task_service.py). The `claude_fix`
step exists but is not part of the default sequence.

### queue
The ordered list of pending steps for tasks, persisted to
`<workspace>/.agentflow/queue.json`. Items are added by
[`queue_service.add_steps`](../backend/agentflow/queue_service.py); each item has a
`status` (queued / running / succeeded / failed / blocked). See [DATA_MODEL.md](DATA_MODEL.md).

### dispatcher
The background loop ([`queue_service.dispatcher_loop`](../backend/agentflow/queue_service.py)
and `tick`) that drives the queue forward. On each tick it finalizes finished runs,
processes at most one controller consult, then picks one dispatchable item
(`_pick_candidate`: queue order, one run per provider lane at a time, intra-task order
preserved) and runs it via `dispatch_item`. It must survive any exception. See
[ARCHITECTURE.md](ARCHITECTURE.md).

### approval
A recorded request to authorize a risky action before it runs, persisted to
`<workspace>/.agentflow/approvals.json` by
[`state_store.create_approval`](../backend/agentflow/state_store.py). An approval has a
status (`pending` / `approved` / `rejected`); resolving it emits an `approval.granted` or
`approval.rejected` event. The raw action is kept on disk so an approved command replays
verbatim, while the displayed copy is redacted. See [SECURITY.md](SECURITY.md).

### workspace
The git repository CLITC is operating on. Per-workspace state lives under
`<workspace>/.agentflow/` (`config.json`, `usage.json`, `tasks/`, `events.json`,
`runs.json`, `approvals.json`, `queue.json`, `chat.json`) — plaintext JSON, atomically
written, with no database. Global state lives in `~/.agentflow/`. See
[DATA_MODEL.md](DATA_MODEL.md) and [CONFIGURATION.md](CONFIGURATION.md).

## Events, runs & streaming

### canonical event / event bus
The single live event stream for the UI. The in-process, workspace-scoped
[`event_bus.BUS`](../backend/agentflow/event_bus.py) assigns every event a
process-monotonic `id`, redacts it, and appends it to a bounded ring buffer (`MAX_BUFFER =
4000`). Events carry typed fields (`type`, `provider`, `taskId`, `runId`, `step`,
`channel`, `textDelta`, `data`, …). Redaction happens here as a defense-in-depth boundary
— secrets are never broadcast or persisted. See
[live-output-everywhere.md](live-output-everywhere.md) and
[text-streaming-across-the-board.md](text-streaming-across-the-board.md).

### SSE cursor
The resume mechanism for the event stream. Readers consume events by `id` and resume from
the last `id` they saw, so a refresh or reconnect never duplicates text. Consumed by
`GET /api/events` (polling fallback) and `GET /api/events/stream` (SSE);
[`event_bus.events_after`](../backend/agentflow/event_bus.py) returns oldest-unseen-first so
advancing the cursor never drops events. The durable ledger
([`state_store`](../backend/agentflow/state_store.py)) has its own independent `cursor`.
See [API.md](API.md).

### run / RunRecord / run ledger
A **run** is one spawned subprocess. The in-memory **`RunRecord`**
([`process_runner.py`](../backend/agentflow/process_runner.py)) holds its argv, cwd,
provider/step/task linkage, captured stdout/stderr, status (`running | succeeded | failed
| cancelled | error`), `failure_kind`, `headroom_applied`, and a per-run monotonic `seq`.
Because in-memory records vanish on restart, `RunRecord.to_ledger` projects a durable,
redacted, tailed view into the **run ledger** `<workspace>/.agentflow/runs.json`
([`state_store.persist_run`](../backend/agentflow/state_store.py)). Failure kinds include
`provider_missing`, `auth_required`, `policy_denied`, `timeout`, `exit_nonzero`,
`cancelled`, `backend_restart` (see `state_store.FAILURE_KINDS`). On restart,
`recover_workspace` settles every still-`running` run as `backend_restart` so nothing is
stuck running forever. Long agent runs are capped at `AGENT_RUN_TIMEOUT` (20 minutes). See
[ARCHITECTURE.md](ARCHITECTURE.md).

## Directives & contracts

### directive
A fenced markdown block the controller emits to take an action, parsed by
[`chat_directives.py`](../backend/agentflow/chat_directives.py). The five kinds:
- ` ```agentflow-task ` — create a task (`title:`, `goal:`, optional `queue:`).
- ` ```agentflow-queue ` — queue steps onto a task (`task:`, `steps:`).
- ` ```agentflow-run ` — run a command (`command:`; capped at `MAX_RUN_DIRECTIVES = 3`).
- ` ```agentflow-done ` — finish (`reason:`).
- ` ```agentflow-needs-user ` — hand back to the user (`reason:`).

`controller_directive_records` validates the parsed blocks into the deterministic
contracts below. See [PILLARS.md](PILLARS.md) (Pillar 5).

### deterministic contract / kind / version
The deterministic semantic layer (Pillar 5): versioned, `kind`-discriminated Pydantic
models in [`contracts.py`](../backend/agentflow/contracts.py) sitting between the canonical
event envelope and the frontend presentation model. Every contract carries a `version`
(currently `CONTRACT_VERSION = "1"`) and a `kind` discriminator. Kinds include the
controller directives (`task`, `queue`, `run`, `done`, `needs_user`) plus result/summary
contracts (`command_summary`, `test_summary`, `failure`, `approval_request`,
`task_summary`, `agent_handoff`, `token_efficiency_report`). `contracts.validate(kind,
data)` returns either a model or a structured `FailureRecord` — unknown kinds, unsupported
versions, and schema violations fail **safely**, never raising. See [PILLARS.md](PILLARS.md)
(Pillar 5).

### agent hand-off
The structured summary passed from one agent step to the next so the next agent gets a
compact, token-efficient brief instead of raw context. The `agent_handoff` contract
(`fromStep`, `toStep`, `provider`, `summary`, `artifacts`) in
[`contracts.py`](../backend/agentflow/contracts.py); markdown handoff artifacts in the task
directory are the human-readable counterpart. See [PILLARS.md](PILLARS.md) (Pillars 1 & 5).

## Policy & safety

### policy classify (allow / require_approval / deny)
The command-policy gate in [`policy_service.py`](../backend/agentflow/policy_service.py),
the single source of truth for whether a command may run.
[`classify_action`](../backend/agentflow/policy_service.py) returns a `PolicyResult` with
one of three decisions:
- **`allow`** — low-risk, workspace-confined reads/checks and agent steps.
- **`require_approval`** — shared/remote-state changes (installs, `git push/pull`, `gh`,
  `npm install`, deploy/publish, code runners like `make`/`npx`) — routed through the
  approval flow.
- **`deny`** — shell operators, env-var prefixes, blocked binaries (`sudo`, `bash`, `dd`,
  …), inline-eval (`python -c`, `node -e`), path traversal / paths outside the workspace,
  and known exec-bypass vectors (`git -c`, `tar --checkpoint-action`, …). Denied actions
  never run.

`deny_reason` is a thin backward-compatible wrapper that only reports hard denials. See
[SECURITY.md](SECURITY.md) and
[ADR-0001](adr/0001-auto-run-policy-allowlist.md).

### redaction
Stripping secret-looking values (PEM private keys, GitHub/OpenAI/Slack/AWS/Google tokens,
bearer headers, `KEY=value` secrets, URL credentials) from any text before it is persisted
or broadcast. Implemented in [`redaction.py`](../backend/agentflow/redaction.py) (`redact`
for strings, `redact_data` for JSON structures) and applied at the event bus, run ledger,
and provider-check log boundaries. Redaction never happens in the browser. See
[SECURITY.md](SECURITY.md).

## Headroom (token saving)

### Headroom / proxy / savings profile
[Headroom](../backend/agentflow/headroom_service.py) is an optional, **fail-open**
context-optimization layer (Pillar 1) that sits between an agent CLI and its model
provider to compress prompt context and cut tokens. When enabled
(`headroom.enabled` in global config) and the **proxy** is reachable, CLITC injects the
proxy as the agent's base URL — `ANTHROPIC_BASE_URL` for `claude`, `OPENAI_BASE_URL` (+`/v1`)
for `codex`. The proxy default is `http://127.0.0.1:8799` (deliberately *not* `:8787`).
Reachability is a bounded 300 ms TCP probe with a 5 s cache; if it is disabled, down, or
slow, the agent runs directly against its provider — Headroom is never required. The
**savings profile** (compression aggressiveness / accuracy guard) is the proxy's concern,
started with [`scripts/headroom.sh`](../scripts/headroom.sh). See [PILLARS.md](PILLARS.md)
(Pillar 1).

### headroom agent-90
The default `savingsProfile` value (`agent-90`) in
[`headroom_service.py`](../backend/agentflow/headroom_service.py) `_DEFAULTS`. It names the
`headroom agent-savings` profile that the proxy is started with; CLITC only points agents
at the proxy and reports the configured profile name — it does not itself measure token
savings (the `token_efficiency_report` contract leaves token counts `null` unless the proxy
provides them). See [PILLARS.md](PILLARS.md) (Pillar 1).

## Presentation (frontend)

### presentation model / card taxonomy
The shared deterministic display layer in
[`frontend/src/lib/displayModel.ts`](../frontend/src/lib/displayModel.ts). The backend emits
structured records; the UI renders them by **`CardType`** rather than by parsing agent
prose. The fixed **card taxonomy** (`CardType`) includes `TASK_CREATED`, `TASK_BRIEF`,
`STATE_TRANSITION`, `QUEUE_ITEM`, `RUN_STARTED`, `RUN_OUTPUT`, `COMMAND_RESULT`,
`APPROVAL_REQUIRED`, `APPROVAL_RESOLVED`, `DIFF_SUMMARY`, `ARTIFACTS_CHANGED`, `QA_STATUS`,
`FAILURE`, `SCHEDULED_OVERFLOW`, `FINAL_SUMMARY`, `NEEDS_USER`. Each result splits into three
channels — `ActionData` (strict structured fields), `HumanSummary` (a fixed shape, ≤5
bullets), and `DisplayData` (the `CardModel` that drives a card/badge/status). `CARD_STYLE`
maps each card type to one shared dot/accent so the same event looks identical in the
compact Agent Dock and the detailed Tasks page. See [PILLARS.md](PILLARS.md) (Pillars 3 & 4)
and [task-controller-io-surface.md](task-controller-io-surface.md).

## Terminals & serving

### PTY terminal session
A real pseudo-terminal subprocess (the shell from `$SHELL`) managed by
[`terminal_service.py`](../backend/agentflow/terminal_service.py), exposed to the browser
(xterm.js) over a WebSocket. Session state lives under `~/.agentflow/run/terminals/`. WS
origins are restricted by the origin allowlist
([`origins.py`](../backend/agentflow/origins.py)). See [ARCHITECTURE.md](ARCHITECTURE.md)
and [OPERATIONS.md](OPERATIONS.md).

### single-port mode
The production serving mode where the FastAPI backend serves the built frontend
(`frontend/dist`) directly on `127.0.0.1:8787` — no separate Vite dev server. When `dist/`
exists, [`app.py`](../backend/agentflow/app.py) mounts `/assets` and serves `index.html`,
confining all paths to `dist`. In development the Vite dev server runs on `:5180` and
proxies `/api` to the backend instead. See [OPERATIONS.md](OPERATIONS.md) and
[GETTING_STARTED.md](GETTING_STARTED.md).
