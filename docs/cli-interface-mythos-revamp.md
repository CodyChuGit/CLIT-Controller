# CLI Interface Mythos Revamp

This is the implementation brief for a Fable5 / Mythos-level rebuild of the
CLI interface surfaces in CLIT Controller IDE.

The product move is simple: stop treating the app as a chat panel plus task
logs, and treat it as a visual control room for local CLI agents. The UI should
let non-terminal users see what Codex, Claude, Antigravity, shell commands, and
the controller are doing in real time, while the backend keeps the same local
CLI, workspace, policy, queue, and approval boundaries.

## Source Review

Reviewed current docs and code paths:

- Product direction: `DESIGN.md`, `docs/live-output-everywhere.md`,
  `docs/text-streaming-across-the-board.md`,
  `docs/streaming-renderer-decision.md`,
  `docs/task-controller-io-surface.md`,
  `docs/vscode-style-agent-dock.md`,
  `docs/orchestrator-backend/*`, `docs/FEATURE_STATUS.md`.
- Right-hand dock: `frontend/src/components/ChatPanel.tsx`,
  `frontend/src/hooks/useDockData.ts`, `frontend/src/stream.tsx`,
  `frontend/src/components/SmoothStreamingText.tsx`,
  `frontend/src/components/conversation/Message.tsx`.
- Controller backend: `backend/agentflow/chat_service.py`,
  `backend/agentflow/controller_protocol.py`,
  `backend/agentflow/prompt_templates.py`, `backend/agentflow/io_contracts.py`,
  `backend/agentflow/process_runner.py`, `backend/agentflow/event_bus.py`.
- Terminals: `frontend/src/pages/TerminalsPage.tsx`,
  `backend/agentflow/terminal_service.py`,
  `backend/agentflow/api/routes_terminals.py`,
  `backend/agentflow/provider_probe.py`.
- Tasks page: `frontend/src/pages/TasksPage.tsx`,
  `frontend/src/pages/tasks/TaskFlowChart.tsx`,
  `frontend/src/pages/tasks/StepChat.tsx`,
  `frontend/src/pages/tasks/TaskStatusPanels.tsx`,
  `frontend/src/pages/tasks/taskPageModel.ts`,
  `frontend/src/lib/displayModel.ts`,
  `frontend/src/components/TaskViews.tsx`.

No file named `Agent_CLI_Skill` exists in this workspace by exact search. This
brief maps that concept to the app's local CLI-agent contract:

- official user-installed CLIs are the runtime
- stdout/stderr and PTY output are primary live signals
- the backend owns policy, approvals, workspace confinement, redaction, and
  durable state
- the UI visualizes the CLI workflow for non-terminal users
- structured controller decisions drive mutations; prose is display only

## North Star

CLIT Controller becomes a CLI agent mission-control surface:

- Live generated text appears as it is produced, not after cached chat/log
  snapshots settle.
- The right-hand Agent Dock becomes the live command center.
- The controller backend becomes a deterministic CLI workflow engine.
- The Antigravity `agy` terminal becomes a debuggable PTY session with explicit
  launch and readiness state.
- The Tasks page becomes a task-distribution workbench that explains which agent
  has which work, why it was routed there, what is blocked, and what changed.

## Non-Negotiables

- Keep local-first CLI execution. Do not replace provider CLIs with hosted APIs.
- Keep the backend authoritative for redaction, events, queue, policy, approvals,
  and workspace confinement.
- Keep one workspace-scoped event stream. Do not add page-owned SSE streams.
- Render active output from live event deltas, not cached `chat.json`, logs, or
  `outputTail` snapshots.
- Preserve raw detail, but make human-readable cards the default surface.
- Rebuild behind stable seams where possible. Preserve route names unless a new
  versioned route is required.

## Current Gaps

### Agent Dock

Current strengths:

- `EventStreamProvider` owns one SSE/polling stream.
- `streamStore` accumulates per-run deltas.
- `SmoothStreamingText` is presentation-only and does not own network state.
- `ChatPanel` already has controller/provider tabs, command palette, approvals,
  run activity, and pending live output.

Current gaps:

- `ChatPanel` still mixes live stream data with `pending.outputTail`,
  `api.logs().running`, and polling snapshots.
- Structural events are not fully projected into compact controller cards in the
  dock, even though `cardFromStreamEvent` exists.
- Active output is visible, but the dock still reads like chat plus activity,
  not a full CLI-agent toolbar.
- There is no terminal drawer in the dock; users must leave the dock for the
  Terminals page.

### Traffic Controller Backend

Current strengths:

- Prompts already instruct the controller to emit `CLITC_RESULT_V1`.
- `controller_protocol.py` validates a closed action union.
- `process_runner` streams `controller.delta`, `chat.delta`, `run.output`, and
  command lifecycle events.
- `state_store` and `event_bus` provide durable structural events plus live
  streaming.

Current gaps:

- `chat_service.send` strips `CLITC_RESULT_V1` for display, but task creation,
  queueing, and commands still execute through legacy `agentflow-*` directive
  parsers.
- `orchestrator_consult` still parses legacy queue/done/needs-user blocks
  instead of executing validated `ControllerResult.action`.
- Deterministic result and summary schemas are validated in tests, but not yet
  the live mutation path.
- Controller action execution, projection, validation, and policy gating are all
  tangled inside `chat_service.py`.

### Agy Terminal

Current strengths:

- The Terminals page uses real xterm.js panes over PTY WebSockets.
- Backend sessions survive socket reconnects and replay scrollback.
- Provider probing resolves `agy` through normal PATH plus `~/.local/bin`.
- Antigravity is launched bare on purpose, avoiding swallowed startup prompts.

Current gaps:

- The Antigravity pane exposes only `connected` / `disconnected`; it does not
  show executable resolution, launch command, auth/init state, readiness, or
  crash reason.
- Server-to-client WS frames are raw terminal bytes only, so UI state cannot
  distinguish "PTY connected but `agy` failed to launch" from "TUI is still
  initializing".
- `launch_command(provider)` returns only the basename of the resolved binary.
  That depends on child PATH being correct instead of using the resolved path as
  the launch source of truth.
- No terminal diagnostics endpoint tells the UI why the `agy` box did not load.

### Tasks Page

Current strengths:

- Task details include deterministic `stepPreviews`, runs, exchanges, queue
  state, approvals, changed files, and events.
- `TaskFlowChart`, `StepChat`, `StateCard`, `QueueStrip`, `TimelineCard`, and
  `RawDetail` provide useful primitives.
- Selected active step output can read live run deltas with `useRunStream`.

Current gaps:

- The page is still a centered scroll page with a linear step chart and a grid of
  step cards.
- It does not clearly explain task distribution across provider lanes.
- Queue, approvals, live run, artifacts, events, and final summary are separate
  sections rather than one coherent task-control model.
- "Continue task" sends the user to the controller dock for the reply, which
  breaks locality for task review.

## Workstream 1: Right-Hand Agent Dock Rebuild

### Target Shape

The right-hand dock becomes the Agent Toolbar:

```text
+------------------------------------------------+
| controller | codex | claude | antigravity      |
+------------------------------------------------+
| Mission strip: workspace, branch, mode, health |
+------------------------------------------------+
| Live transcript / event cards                  |
| - user prompt                                  |
| - controller narrative delta                   |
| - action card: create task / queue / command   |
| - live CLI output                              |
| - approval hold / blocker / completion         |
+------------------------------------------------+
| Terminal drawer or split pane                  |
+------------------------------------------------+
| Composer: provider, chips, prompt, actions     |
+------------------------------------------------+
| Status footer: queue, runs, stream, provider   |
+------------------------------------------------+
```

### Data Rule

Active runs must render from `streamStore` only:

- `controller.delta` and `chat.delta` for live narrative
- `run.output` and `run.stderr` for managed run output
- `command.started` / `command.finished` for shell command cards
- `approval.*`, `queue.*`, `task.*`, and `controller.decision_received` for
  structural cards

Allowed fallback:

- If SSE is unavailable, the existing `/api/events?cursor=` polling path remains
  the source because it reads the same event bus.

Not allowed for active output:

- `pending.outputTail` as the primary text source
- `api.logs().running` as the primary text source
- final chat messages replayed through a fake typewriter effect

### Component Plan

Refactor `ChatPanel.tsx` into:

- `AgentDock.tsx`: frame, resize, collapsed rail, tab ownership.
- `AgentDockTabs.tsx`: controller and provider tabs with unread/running state.
- `AgentDockTranscript.tsx`: event-card and message rendering.
- `AgentDockLiveRun.tsx`: consumes `useRunStream(runId)` only.
- `AgentDockTerminalDrawer.tsx`: provider-scoped xterm drawer.
- `AgentDockComposer.tsx`: wraps `InputComposer` with provider/mode/context
  chips.
- `AgentDockFooter.tsx`: stream health, queue state, run count, provider health.

Keep the existing primitives:

- `InputComposer`
- `Message`
- `TimelineCard`
- `ApprovalCard`
- `SmoothStreamingText`
- `CommandPalette`
- provider marks

### Dock Acceptance Criteria

- A controller response starts rendering from `controller.delta` before the CLI
  exits.
- Direct provider chat starts rendering from `chat.delta` before the CLI exits.
- Managed task/command output appears in the dock from live run events.
- No active generated text comes from cached final messages or log snapshots.
- Structural events render as compact cards using the shared display model.
- The terminal drawer can open without navigating away from the dock.
- Completed messages become static and do not reanimate.

## Workstream 2: Traffic Controller Backend Rebuild

### Rebuild Boundary

Do not rewrite the whole backend. Rebuild the traffic controller internals behind
the current API seams:

- `/api/chat/send`
- `/api/chat/submit`
- `/api/chat/direct`
- `/api/tasks/*`
- `/api/queue/*`
- `/api/events*`

The current `chat_service.py` should stop being the controller engine. It should
become a thin API-facing facade.

### New Backend Modules

Create a small controller package:

```text
backend/agentflow/controller/
  engine.py          # builds turns, starts CLI runs, parses CLITC_RESULT_V1
  actions.py         # validates and executes ControllerAction values
  projectors.py      # ControllerResult -> events, cards, summaries
  context.py         # workspace/task/usage/queue prompt context
  adapters.py        # provider-specific CLI launch details
  errors.py          # typed controller failure states
```

### Controller Flow

```text
InputSubmission
  -> ControllerTurn
  -> provider CLI run
  -> live narrative deltas
  -> CLITC_RESULT_V1 parse
  -> validated ControllerAction
  -> policy / queue / task mutation
  -> durable events
  -> display projection
  -> next queue dispatch or user action
```

### Action Execution

The only authoritative controller mutation path should be
`ControllerResult.action`:

- `answer`: store assistant summary, no mutation
- `create_task`: create task, write handoff files, optionally queue first steps
- `queue_steps`: validate task and steps, add queue items
- `run_command`: classify policy, run safe command or create approval
- `request_approval`: create durable approval without running
- `request_user`: mark task/dock state as needs-user
- `retry`: retry selected queue item or task step
- `reroute`: validate provider and step, queue provider override
- `complete_task`: write final verdict and summary event
- `cancel`: cancel selected run or all active runs

Legacy `agentflow-*` directive parsing should move to a migration fallback:

- behind a feature flag or compatibility path
- emits a warning event
- never preferred when a valid `CLITC_RESULT_V1` block exists

### State Machine

Add explicit controller turn records:

```json
{
  "id": "turn_...",
  "workspacePath": "...",
  "source": "controller_chat | consult | task_continue",
  "provider": "antigravity",
  "taskId": "optional",
  "runId": "run_...",
  "status": "running | actioned | needs_user | failed | cancelled",
  "resultSource": "clitc_result_v1 | legacy | none",
  "actionType": "queue_steps",
  "createdAt": "...",
  "completedAt": "..."
}
```

Store these under `.agentflow/controller_turns.json` or as typed events in the
existing event ledger.

### Prompt Contract

Prompt templates should be generated from `controller_protocol.ACTION_TYPES` and
schemas. The prompt must say:

- stream human-readable narrative first
- end with exactly one `CLITC_RESULT_V1` block
- nothing after the sentinel
- invalid JSON means no action is taken

### Backend Acceptance Criteria

- `chat_service.send` executes a valid `CLITC_RESULT_V1` action without relying
  on legacy directive parsers.
- `orchestrator_consult` executes a valid `CLITC_RESULT_V1` action.
- Invalid result blocks produce a typed failure event and no state mutation.
- Multiple result blocks use the last valid block and emit a misbehavior signal.
- Every controller action emits structured events and a display projection.
- Existing policy and approval gates still own command execution.
- Existing queue provider-concurrency rules still apply.

## Workstream 3: Rebuild The Antigravity Agy Terminal Box

### Product Target

The Antigravity terminal should not be a black box that says only
`disconnected`. It should show a clear lifecycle:

```text
resolving executable
  -> launching agy
  -> PTY connected
  -> initializing TUI
  -> ready for input
```

If it fails:

```text
missing executable
auth required
launch crashed
PTY closed
backend disconnected
```

### Backend Terminal Adapter

Add a provider terminal adapter:

```python
class TerminalLaunchSpec(BaseModel):
    provider: str
    executablePath: str | None
    argv: list[str]
    shellLaunch: str
    cwd: str
    launchMode: Literal["bare_tui", "shell"]
    startupNote: str
```

Rules for Antigravity:

- resolve provider `antigravity` to the actual `agy` or `antigravity` binary
- prefer the resolved executable path over basename-only launch
- launch bare TUI only; do not pass starter prompts
- keep `TERM=xterm-256color` and user-bin PATH additions
- expose auth/init text in the terminal output, but also classify common
  patterns into metadata when possible

### WebSocket Frame Contract

Keep binary frames for raw PTY bytes, but allow JSON text frames from server to
client:

```json
{"type":"meta","state":"launching","provider":"antigravity","executablePath":"/Users/me/.local/bin/agy"}
{"type":"meta","state":"ready","provider":"antigravity"}
{"type":"meta","state":"closed","exitCode":1,"reason":"pty_closed"}
```

Frontend behavior:

- binary frames go to xterm
- JSON `meta` frames update pane state
- non-JSON text frames still write to xterm for compatibility

### Diagnostics Endpoint

Add:

```text
GET /api/terminals/{provider}/diagnostics
```

Return:

```json
{
  "provider": "antigravity",
  "installed": true,
  "executablePath": "/Users/me/.local/bin/agy",
  "workspace": "/path/to/ws",
  "sessionState": "ready | missing | launching | closed",
  "lastLaunchError": null,
  "suggestedAction": null
}
```

### Frontend Terminal Pane

Rebuild `TerminalPane` into:

- `TerminalPaneShell`: frame and controls
- `XtermSurface`: xterm ownership only
- `TerminalConnectionStatus`: resolving, launching, connected, ready, auth,
  crashed, reconnecting
- `TerminalDiagnostics`: visible on failure

Keep the xterm surface visually stable. Do not show a loading card instead of
the terminal; show lifecycle status in the header and an inline diagnostic strip.

### Agy Terminal Acceptance Criteria

- The Antigravity pane shows the resolved `agy` path or a specific missing-binary
  state.
- Restart kills the old session, starts a fresh one, and shows the new lifecycle.
- Backend reconnects replay scrollback and current meta state.
- A PTY can be connected while `agy` is still initializing; the UI communicates
  that instead of calling it failed.
- Tests cover executable resolution, diagnostics, WS metadata frames, unknown
  provider gating, no-workspace gating, and restart.

## Workstream 4: Rethink The Tasks Page

### Product Target

The Tasks page should explain distribution, not just execution history.

The user should understand:

- what the task is trying to accomplish
- which agent owns each piece of work
- why the controller routed work there
- what is active right now
- what is blocked and what action is needed
- what changed in files/artifacts
- what raw evidence exists if they need to inspect it

### Target Layout

```text
+------------------------------------------------------------------+
| Mission Bar: task title, state, active step, provider health      |
+---------------------+-----------------------------+--------------+
| Task Queue          | Dispatch Map                | Inspector    |
| - active            | Controller lane             | selected run |
| - needs approval    | Codex lane                  | artifacts    |
| - failed            | Claude lane                 | approvals    |
| - scheduled         | Antigravity lane            | raw detail   |
| - done              | Local tools lane            | diff/logs    |
+---------------------+-----------------------------+--------------+
| Live CLI Stream for selected active run                          |
+------------------------------------------------------------------+
```

### Dispatch Map

Replace the linear `TaskFlowChart` with provider lanes:

- Controller lane: decisions, task creation, routing, final verdict.
- Codex lane: specs, plans, reviews.
- Claude lane: implementation and fixes.
- Antigravity lane: traffic control and QA.
- Local tools lane: shell commands, git, tests, dev server.

Each lane shows:

- queued item cards
- active run card with live output
- completed result cards
- blocked/approval cards
- artifacts and changed-file chips

This directly explains how agentic flow distributes tasks.

### Inspector

The right inspector changes based on selection:

- task selected: final summary, task brief, next actions
- run selected: live output, command, duration, exit code, log link
- provider lane selected: provider role, health, active/queued work
- approval selected: command, reason, approve/reject
- artifact selected: markdown, diff, log, raw event detail

### Live Task Output

The selected active run should use `useRunStream(runId)` and `SmoothStreamingText`
from the shared event store. Finished history should render statically from
durable events and task exchanges.

### Component Plan

Replace or split current components:

- `TasksPage.tsx` -> page shell and selected-task orchestration only
- `TaskMissionBar.tsx` -> current `StateCard` plus routing and health
- `TaskQueueRail.tsx` -> task list plus queue filters
- `TaskDispatchMap.tsx` -> provider lanes replacing `TaskFlowChart`
- `ProviderLane.tsx` -> lane-owned cards and active output
- `TaskInspector.tsx` -> selected item detail
- `TaskLiveStream.tsx` -> selected active run live output
- `TaskArtifactsPanel.tsx` -> markdown, diffs, logs, raw details

Reuse:

- `TimelineCard`
- `RawDetail`
- `ApprovalCard`
- `CommandCard`
- `InputComposer`
- `displayModel.ts`

### Task Page Acceptance Criteria

- A user can tell which provider is doing what without opening step cards.
- Active run output appears in the selected lane and live stream before finish.
- Queue blockers and approvals are visible in context, not isolated below the
  fold.
- Routing rationale and provider health are visible near the work they affect.
- Raw prompts, stdout, stderr, logs, JSON, and events remain paginated detail.
- The page works as a review surface after refresh or backend restart.

## Shared Event And Display Contract

The frontend should increasingly consume typed payloads from `event.payload`
instead of open-ended `event.data`.

Add display projection events where needed:

```json
{
  "type": "display.card",
  "card": {
    "type": "QUEUE_ITEM",
    "display": {
      "title": "Queued",
      "severity": "info",
      "provider": "claude",
      "step": "claude_implement",
      "summary": {"title":"Queued", "bullets":["Implementation queued after spec"]}
    }
  }
}
```

This keeps the UI from parsing prose and lets the dock and Tasks page render the
same state at different densities.

## Implementation Phases

### Phase 0: Characterize Current Behavior

- Add focused tests for controller result parsing in live chat and consult paths.
- Add a terminal diagnostics test scaffold with fake provider resolution.
- Add frontend unit tests around `streamStore` active-output sources.

### Phase 1: Live Output Hardening

- Remove active-output dependency on `pending.outputTail` and `api.logs().running`
  in dock rendering.
- Render controller/provider pending output from `useRunStream(runId)`.
- Render structural stream events as `TimelineCard` compact cards in the dock.
- Keep polling snapshots only for structural refresh, not live text.

### Phase 2: Controller Engine Extraction

- Create the controller package.
- Move prompt context building out of `chat_service.py`.
- Execute `ControllerResult.action` as the primary mutation path.
- Demote legacy directive parsing to compatibility fallback.
- Emit typed controller turn events.

### Phase 3: Agent Dock UI Rebuild

- Split `ChatPanel` into dock subcomponents.
- Add terminal drawer.
- Add mission strip and footer.
- Add compact event-card transcript.
- Keep the composer and command palette.

### Phase 4: Agy Terminal Rebuild

- Add terminal launch specs and diagnostics.
- Use resolved executable path for Antigravity launch.
- Add WS metadata frames.
- Rebuild `TerminalPane` around explicit lifecycle state.
- Add tests for diagnostics and metadata.

### Phase 5: Tasks Workbench Rebuild

- Replace step chart/grid with task queue rail, provider-lane dispatch map,
  inspector, and live stream.
- Keep raw detail and artifacts in inspector panels.
- Add routing rationale and provider health near lanes.
- Support task continuation locally in the task context, while still sending
  through the controller backend.

### Phase 6: Verification And Cleanup

- Remove dead legacy UI paths.
- Update `FEATURE_STATUS.md` after behavior is real.
- Update `FRONTEND.md`, `BACKEND.md`, and `API.md` for new seams.
- Run the smallest reliable checks: targeted backend tests, targeted frontend
  component tests, then one build if frontend structure changed.

## Verification Matrix

Backend:

- controller result valid action -> state mutation
- controller result invalid JSON -> no mutation, failure event
- controller consult uses `CLITC_RESULT_V1`
- legacy directive fallback emits compatibility warning
- stream emits `controller.delta` before process exit
- command approval still gates risky commands
- terminal diagnostics for missing and installed `agy`
- terminal WS sends metadata frames and binary PTY bytes

Frontend:

- dock pending output uses `useRunStream(runId)`
- completed chat messages do not animate
- compact event cards render queue, approval, command, and task events
- terminal pane shows launching/ready/missing/crashed states
- task dispatch map groups work by provider lane
- selected run live stream updates from shared event store
- raw detail remains paginated and copyable

Manual local checks:

- Start controller chat and confirm text appears before completion.
- Start direct provider chat and confirm text appears before completion.
- Queue a task and confirm dock and Tasks page show the same active run.
- Open Antigravity terminal and confirm lifecycle status plus xterm output.
- Kill/restart Antigravity terminal and confirm a fresh session.

## Definition Of Done

- The right-hand toolbar feels like a native CLI-agent cockpit, not cached chat.
- The controller backend mutates state from validated `CLITC_RESULT_V1` actions.
- The Antigravity terminal tells the user exactly where launch failed or when it
  is ready.
- The Tasks page explains distributed agent flow through provider lanes,
  queue/approval context, live streams, artifacts, and inspector detail.
- All active output comes from the shared event stream.
- Raw terminal/log/detail access remains available without becoming the default
  reading experience.
