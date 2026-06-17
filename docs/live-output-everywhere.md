# Live Output Everywhere

CLIT Controller IDE should make assistant work feel immediate, readable, and
continuous across the app. Generated content should appear as soon as it is
generated or received, similar to native LLM chat experiences, while still
preserving the durable task history designers need for review.

This is the product package for the live-output roadmap item. The lower-level
event contract lives in [Text Streaming Across The Board](./text-streaming-across-the-board.md),
the renderer decision lives in [Streaming Renderer Decision](./streaming-renderer-decision.md),
and the shared task/controller display model lives in
[Task And Controller I/O Surface](./task-controller-io-surface.md).

## Product Story

Designers should not have to wait for a hidden run to finish before they know
whether the assistant understood the task. When Codex, Claude Code,
Antigravity, or the controller starts working, CLIT Controller should show
progress immediately:

- the first generated words in a chat reply
- command output as it arrives
- task status changes as they happen
- approval waits before the queue feels stuck
- logs and failures while there is still time to react
- final summaries that settle into the same task history

The experience should feel like watching a strong LLM chat client, but expanded
across the full design workflow: chats, tasks, logs, approvals, queues, and
reviews all update from the same live record.

## User Promise

Live Output Everywhere means:

- **No blank waiting state**: active work shows progress before completion
  whenever the underlying assistant or process emits output.
- **No final-only snapshots**: text does not appear only after the full run has
  finished.
- **No duplicate stories**: the live view and completed task replay are built
  from the same events.
- **No terminal hunting**: designers can understand active progress from the
  app without opening separate terminal windows.
- **No fake typing**: smoothing improves readability, but CLIT Controller should
  display real generated or received output.

## Experience Principles

### 1. Native LLM Chat Feel

Assistant responses should stream progressively into the visible conversation.
The user sees the reply take shape, can stop early if it is going in the wrong
direction, and does not lose time waiting for a completed blob of text.

Expected behavior:

- New generated text appears in-place as deltas arrive.
- The active response uses smooth pacing for readability.
- Finished responses become stable text and do not animate again.
- Reduced-motion users see immediate text without animation.
- Long output stays scroll-contained and does not push the whole interface
  around.

### 2. One Live Record

Every surface should observe the same workspace event stream. The Agent Dock,
Tasks page, Logs page, status bar, and approval surfaces should not invent
separate polling loops or disagree about what happened.

The user should be able to start in the dock, switch to Tasks, and see the same
run still progressing with the same output.

### 3. Designer-Readable First

Live output should not turn the UI into raw terminal scrollback. CLIT Controller
should show structured, readable progress first, with raw detail available when
needed.

Examples:

- "Claude Code is editing the calendar card layout" before raw stdout.
- "Approval required for file changes" before a raw command block.
- "3 files changed" before a long diff.
- "Run failed: missing dependency" before full stderr.

### 4. Review Continuity

When a run completes, the live transcript should become the durable task replay.
There should not be one version of events during the run and a different version
after refresh.

The completed review should preserve:

- prompts and assistant output
- command lifecycle events
- stdout and stderr links
- approvals and denials
- queue changes
- changed files and summaries
- final task status

## Surface Package

| Surface | Live Behavior | Settled Review Behavior |
|---|---|---|
| Agent Dock | Streams chat replies, controller decisions, command output, queue changes, approvals, failures, and completion status. | Keeps compact transcript rows with links into the related task. |
| Tasks Page | Streams the selected active task from the same event store as the dock. | Turns the live run into a durable timeline with summaries, raw-detail drawers, and artifacts. |
| Logs Page | Appends redacted events as they happen. | Allows filtering by task, provider, run, channel, and severity. |
| Approvals | Shows approval waits immediately when a run needs user action. | Preserves the approval decision and reason in task history. |
| Queue And Status | Updates active run count, provider state, queue blockers, and streaming health. | Leaves a clear record of run duration, final state, and next action. |
| Terminal Context | Shows managed run output where it belongs; PTY sessions continue to stream separately. | Links terminal output back to task/run context when available. |

## Event Package

The backend remains the source of truth. It should emit redacted, durable events
as work happens, then let frontend surfaces subscribe and render them.

Core event families:

- `chat.*` for direct assistant conversation
- `controller.*` for task creation, routing, and decisions
- `run.*` for assistant or command execution
- `command.*` for process lifecycle and command-level output
- `queue.*` for scheduling, running, pausing, and completion
- `approval.*` for required, granted, rejected, and expired approvals
- `task.*` for status changes and summaries
- `log.*` for redacted global and task logs

Every event should be attachable to the workspace and, when available, the task,
run, provider, queue item, step, channel, and sequence number.

## Rendering Package

The frontend should use one workspace-scoped stream store and a small internal
streaming renderer.

Required behavior:

- subscribe once to the backend event stream
- resume from the last event cursor after refresh
- dedupe repeated events
- accumulate text by run/chat/task
- render visible deltas immediately
- smooth active output with an internal component
- keep completed output static
- fall back to polling without changing the UI model

Do not add a package that owns chat state, opens its own SSE connection, or
creates a fake typewriter effect after the backend already has the full text.

## Interaction Details

### Stop And Reroute

Because output appears while work is still running, designers should be able to
stop a run that is drifting, add clarification, and reroute before more time or
tokens are spent.

### Auto-Tail

Live panels should auto-scroll only while the user is already near the bottom.
If the user scrolls up to inspect earlier output, new chunks should not steal
their position.

### Long Output

Large command output should stay inside bounded regions with raw-detail links.
The primary surface should show the meaningful state first, not thousands of
lines of text.

### Errors

Failures should appear as readable status cards as soon as they are detected,
with raw stderr and logs available behind details.

### Approvals

Approval-required states should interrupt the active surface clearly. The user
should see what is waiting, why it is waiting, and what action is available.

## Rollout Plan

### Phase 1: Shared Event Foundation

- Add durable event IDs and cursor resume.
- Emit run, chat, queue, task, approval, and log events.
- Keep polling endpoints as fallback.
- Redact before persistence and broadcast.

### Phase 2: Live Surfaces

- Wire the Agent Dock, selected Tasks detail, Logs page, status bar, and queue
  indicators to the shared event store.
- Show active output before completion wherever the process emits chunks.
- Keep completed replay sourced from the same events.

### Phase 3: Smooth Native Feel

- Add the internal `SmoothStreamingText` renderer.
- Use it only for active generated output and live command text.
- Respect reduced motion.
- Keep layout stable and scroll behavior predictable.

### Phase 4: Review Polish

- Convert completed live runs into readable task timelines.
- Add raw-detail drawers for stdout, stderr, logs, prompts, and event payloads.
- Improve failure, approval, and diff summary cards.

## Acceptance Criteria

- Starting a provider chat or queued task shows visible progress before the run
  completes whenever output is available.
- Generated text displays as it is generated or received, not only after final
  completion.
- The Agent Dock, Tasks page, Logs page, approvals, queue indicators, and status
  bar consume the same event stream.
- Refreshing the app resumes from a cursor without duplicating text.
- Completed task replay is built from the same events shown during the live run.
- Designers can stop, approve, retry, or reroute while the run is active.
- Long output stays readable and bounded.
- Raw logs remain available without becoming the default reading experience.
- Secrets are redacted before events are stored or displayed.
- The app still works through polling fallback when streaming is unavailable.

## Non-Goals

- Do not replace the CLI-first assistant model with direct provider APIs.
- Do not add a hosted chat SDK.
- Do not use a typewriter animation that starts from already-complete text.
- Do not create separate stream owners per page.
- Do not make raw terminal output the primary product surface.
- Do not bypass existing task, queue, approval, policy, or workspace rules.
