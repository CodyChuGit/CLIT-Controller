# VS Code-Style Agent Dock And Tasks Tab

Command Line Interface Traffic Controller (CLIT Controller IDE) should mimic the
useful parts of VS Code agent plugin panels inside its own native right-hand
dock and Tasks tab. It should not embed VS Code extensions, run a VS Code
extension host, iframe vendor UI, or depend on real VS Code.

## Product Decision

The best path is a two-surface native parity model that feels familiar to users
of Claude Code, Codex, Antigravity, and VS Code side panels while keeping
CLITC's local-first backend, queue, approvals, task files, and CLI execution
model.

This is feasible because CLITC already owns the required primitives:

- A React right-hand chat dock with provider tabs.
- FastAPI chat, task, queue, log, terminal, usage, and provider endpoints.
- CLI-backed direct chats and traffic-controlled task runs.
- PTY-backed live terminal sessions rendered with xterm.js.
- Durable task folders, prompt/output logs, redaction, policy checks, and approvals.

The right-hand dock should evolve these primitives into a polished live agent
workbench. The Tasks tab should evolve the durable task folder and queue views
into the review, history, approval, diff, retry, and final-report surface. Both
are native CLITC product surfaces, not wrappers around VS Code.

Live output is part of the product decision, not a follow-up nice-to-have. During
an active controller, Codex, Claude Code, or Antigravity run, CLITC should show
text as it is generated or received in both the Agent Dock and the selected Tasks
tab detail without making the user open a separate terminal or wait for a final
snapshot.

## Target UX

Right-hand Agent Dock:

- Provider tabs for `controller`, `codex`, `claude`, and `antigravity`, using the
  existing provider marks and unread/running indicators.
- A compact command row with provider picker, mode selector, prompt input, send,
  stop, clear, and command palette actions.
- Chat panes that render user prompts, agent replies, task directives, command
  results, and failures as styled rows instead of raw text dumps.
- Active run streams that type out transcript deltas, terminal output chunks, tool
  or command start/finish events, approval waits, queue changes, errors, and
  completion status as the run progresses.
- Live generated text should use the internal `SmoothStreamingText` renderer over
  CLITC's shared event store so the dock feels like a real CLI without opening a
  second SSE stream or owning separate chat state.
- A terminal drawer per provider for live CLI sessions, reusing the existing
  PTY/WebSocket/xterm.js terminal stack.
- Diff and approval cards for risky actions, failed steps, changed files, and
  queue blockers.
- Queue and task context surfaced as compact status rows: active task, current
  step, provider health, run duration, approval state, and next queued item.
- A bottom status strip matching the app shell: workspace, branch, provider,
  queue state, health, and active run count.
- Command palette actions scoped to CLITC-native actions only, such as run
  step, approve, retry, skip, reroute, open task file, show log, restart terminal,
  and change provider model.

Tasks tab:

- Task list, queue state, and active runs presented as a dense IDE work queue.
- Per-task conversation replay with styled prompt/output exchanges, provider
  marks, step chips, status, elapsed time, and expandable raw details.
- Live output for the selected active task, using the same event stream as the
  Agent Dock. When the run finishes, the live view becomes the durable replay.
- Budget context, repeated command blocks, approvals, failures, and queue updates
  summarized as human-readable cards instead of raw markdown or log dumps.
- Completed task output defaults to readable summaries. Raw prompts, stdout,
  stderr, logs, directives, event payloads, and JSON are paginated drill-down
  views, not the first reading surface.
- Task artifacts grouped into compact tabs or panel sections: task files, diffs,
  logs, approvals, routing decisions, changed files, and final report.
- Continuation controls for retry, skip, reroute, approve, reject, run next step,
  stop run, open log, open task file, and copy command.
- Overflow work caused by user limits, weekly limits, provider health, or budget
  policy is visible as scheduled/overflow queue state and resumes through normal
  CLITC traffic control.

Right-hand UI/UX Reference Tab:

- A dedicated non-provider tab for searchable frontend references, component
  libraries, style recipes, tokens, and extracted examples.
- Reference actions queue normal style-swap tasks and diffs; they do not silently
  rewrite files.

## Architecture

The implementation should keep the current architecture:

- Frontend: evolve `ChatPanel` into an Agent Dock and `TasksPage` into a durable
  parity view, reusing the app shell, tab strip, panel section, status badge,
  markdown, terminal, task view, and icon patterns.
- Backend: keep FastAPI as the single traffic-control boundary. Add data to existing
  endpoints or add narrowly scoped endpoints only when the dock cannot derive a
  stable projection from current responses.
- Execution: keep using official user-installed CLIs through provider templates,
  direct chat commands, task runs, and PTY terminal sessions.
- Safety: keep policy, approval, redaction, workspace confinement, and manual
  approval mode in the backend. The dock should display these states, not bypass
  them.

Future additive interface needs:

- Structured live run events for `run.started`, `run.output`, `run.finished`,
  failures, cancellation, and final summaries.
- Terminal output chunks that can be attached to a provider, task, run, step, and
  log file without duplicating raw log rendering in the UI.
- Tool and command lifecycle events for start, output, finish, error, retry, and
  stop.
- Approval, diff, queue-position, and task-status events that update the dock and
  Tasks tab while work is still running.
- Provider action descriptors for native dock actions.
- Structured approval and diff summaries.
- A unified status projection from queue, runs, terminals, usage, and task state
  that can feed both the dock and Tasks tab.
- Command palette action descriptors with labels, icons, provider scope, disabled
  reasons, and required approval state.
- Structured task exchange summaries: prompt kind, provider, step, budget context,
  commands, raw prompt link, raw output link, elapsed time, result, and artifacts.
- Paginated raw-detail descriptors for prompts, stdout, stderr, logs, events,
  directives, JSON, and large diffs.
- Reference-library descriptors for extracted components, tokens, variants,
  source/license metadata, and style recipes.
- Overflow scheduler descriptors for TestApp Calendar Scheduler handoffs and
  local fallback state.

## Non-Goals

- No `.vsix` execution.
- No VS Code extension host.
- No marketplace plugin loading.
- No vendor webview iframe.
- No `vscode://` deep links, launch actions, or external VS Code controls.
- No direct provider API replacement for the current CLI-first model.
- No action that changes remote state or shared resources without the existing
  approval flow.

## Acceptance Criteria

- The right-hand dock reads as a VS Code-style agent panel while remaining a
  CLITC-native React component.
- The Tasks tab reads as the durable VS Code-style session/history surface for
  the same agents, with equivalent task review and continuation controls.
- Codex, Claude Code, and Antigravity chats are available from provider tabs.
- The controller, queue, task context, approvals, terminals, and logs are visible
  from the dock and Tasks tab without forcing users to read raw CLI output first.
- Active runs show live output in both the Agent Dock and the selected Tasks tab,
  including command output, approval waits, errors, queue changes, and completion.
- Commands, failures, approvals, and diffs use compact styled rows/cards with raw
  details available behind expanders.
- Completed task output is readable by default, with paginated machine-readable
  detail still available.
- The UI/UX reference tab can queue frontend style-swap work without bypassing
  task, diff, and approval workflows.
- Scheduled overflow items are visible in queue/task context and do not appear as
  ordinary failures.
- No feature requires VS Code to be installed or opened.
- Existing backend traffic control, CLI execution, task files, safety policy, and
  approval behavior remain authoritative.
