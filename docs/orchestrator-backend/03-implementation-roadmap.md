# Implementation Roadmap

This roadmap keeps the current architecture recognizable while adding the missing
pieces needed for a fully functional controller backend.

## Phase 0: Baseline And Invariants

Goal: document and lock down current behavior before refactoring.

Tasks:

- Add backend contract tests for the existing task, queue, chat directive, provider,
  usage, redaction, and git services.
- Add fixtures that create a temporary workspace with `.agentflow/`.
- Add state-transition tests for queue dispatch, manual approval mode, red-Claude
  holds, provider-missing skips, and failed-step blocking.
- Add tests for restart simulation where in-memory `RUNNER.runs` is empty but
  `queue.json` contains `running`.
- Add docs for current task markdown handoff files and step IDs.

Acceptance criteria:

- Existing behavior is covered by targeted tests.
- Every current step status and queue status has at least one test.
- Restart loss is captured as a failing or explicitly expected test before it is fixed.

## Phase 1: Durable Run And Event Ledger

Goal: make traffic control recoverable and inspectable.

Tasks:

- Introduce a small persistence layer under `backend/agentflow/state_store.py`.
- Store runs, events, approvals, and queue items in SQLite or versioned locked JSON.
- Keep task markdown files and `task.json` snapshots for human readability.
- Append events for task creation, queue changes, dispatch, run start, run finish,
  policy denial, approval, consult, and final verdict.
- Rebuild `GET /api/logs`, task timeline, and queue state from durable records.
- Add startup recovery for stale running queue items and run records.

Acceptance criteria:

- Backend restart does not leave stale `running` queue items.
- A completed run is visible after restart with command preview, status, prompt file,
  log file, and output tail.
- The task timeline remains complete after restart.

## Phase 2: Explicit State Machines

Goal: make invalid transitions impossible.

Tasks:

- Define task, step, queue item, run, and approval status enums.
- Add transition helpers such as `set_task_status`, `set_step_status`,
  `set_queue_status`, and `finish_run`.
- Route all mutations through transition helpers.
- Reject invalid transitions with logged backend errors.
- Add terminal task verdicts: `done`, `needs_user`, `failed`, `cancelled`,
  `abandoned`.
- Add retry, skip, and reroute queue actions.

Acceptance criteria:

- No service mutates `status` fields directly.
- Invalid transitions are tested.
- A failed step can be retried, skipped, or rerouted without hand-editing queue files.
- The UI receives clear status values for every task and queue item.

## Phase 3: Provider Adapter Layer

Goal: remove provider-specific branching from traffic-control flow.

Tasks:

- Create provider adapters for Codex, Claude, Antigravity, Git/GitHub CLI, Ollama,
  and MLX/omlx.
- Move executable detection, model options, command rendering, auth hints, install
  commands, and failure classification behind the adapter contract.
- Add capability flags per provider.
- Make step routing depend on role plus capability, not hard-coded provider names.
- Preserve current command template customization.
- Add adapter tests with fake executables and fake CLI output.

Acceptance criteria:

- Adding a provider requires a new adapter definition, not changes in task dispatch.
- Provider missing and auth-required failures are classified consistently.
- Command previews still match what will actually run.

## Phase 4: Policy And Approval Engine

Goal: let the controller act autonomously only inside clear safety boundaries.

Tasks:

- Add `policy_service.py` with `classify_action`.
- Validate every `agentflow-run` command through policy.
- Validate provider install, login launch, git remote operations, package installs,
  and deploy/publish commands through policy.
- Add approval records with source, command/action, risk reason, status, createdAt,
  resolvedAt, and resolver.
- Add approval APIs.
- Update manual approval mode to create approval records instead of only changing
  queue item status.
- Ensure approvals are durable and visible after restart.

Acceptance criteria:

- Local safe commands can run automatically.
- Remote-state commands require explicit approval.
- Denied commands never reach `ProcessRunner`.
- Every approval and denial is visible in task events or global logs.

## Phase 5: Typed Controller Decisions

Goal: turn LLM output into validated backend intents.

Tasks:

- Replace one-off regex side effects with a parser that returns a list of decision
  objects.
- Parse all valid directive blocks in a controller response.
- Keep fenced markdown directives for compatibility, but normalize them into typed
  decisions before mutation.
- Add support for retry, skip, reroute, mark done, and request user decisions.
- Add directive parse errors as visible events.
- Consider a strict JSON decision mode later, but do not require it for the first
  full backend milestone.

Acceptance criteria:

- One controller response can create a task and queue multiple validated actions.
- Invalid step names, missing task refs, and denied commands produce useful events.
- A consult that gives no actionable decision marks the task `needs_user`.

## Phase 6: Streaming Observability

Goal: remove stale polling behavior while preserving fallback endpoints.

Tasks:

- Add an event bus backed by durable event IDs.
- Add `GET /api/events/stream` using SSE.
- Emit run output chunks, queue changes, task status changes, provider status changes,
  and approval changes.
- Keep existing polling endpoints for compatibility.
- Update response DTOs so frontend types stay stable.

Acceptance criteria:

- Logs and queue state update live without 2.5-3 second polling delay.
- Reconnecting clients can resume from a cursor.
- Polling still works if SSE is unavailable.

## Phase 7: Context Builder And Artifact Manager

Goal: make agent prompts smaller, more accurate, and easier to audit.

Tasks:

- Create a context builder that selects task files, relevant file paths, git status,
  diff stats, and small excerpts based on step type.
- Add prompt budget estimates before every run.
- Add artifact declarations per step and validate expected files changed.
- Add prompt compression for long task histories.
- Add local summarizer hooks for Ollama/MLX where available.

Acceptance criteria:

- Agents receive consistent, compact context.
- Large diffs are summarized unless the step explicitly requires details.
- Prompt files explain what context was selected and why.

## Phase 8: Full Workflow Polish

Goal: close the loop from user request to final report.

Tasks:

- Add final task report generation from events, artifacts, runs, and git diff.
- Add task export to markdown/HTML.
- Add queue controls for pause/resume at task and global levels.
- Add provider health auto-updates where CLIs expose usage.
- Add project templates for common stacks.
- Add MCP adapter layer after the backend state contracts are stable.

Acceptance criteria:

- A user can inspect a single final report to understand what happened.
- Tasks can be paused, resumed, retried, and completed without editing files.
- The backend is ready for desktop packaging without changing core traffic-control logic.

## Phase 9: VS Code-Style Agent Dock And Tasks Tab

Goal: turn the right-hand chat dock and Tasks tab into native CLITC feature
parity surfaces that feel like VS Code plugin panels without embedding VS Code.

Tasks:

- Evolve the current chat dock into provider tabs for controller, Codex, Claude
  Code, and Antigravity.
- Evolve the Tasks tab into the durable task/session parity surface for history,
  prompt/output replay, diffs, approvals, logs, retries, reroutes, and final
  reports.
- Add a compact command row, command palette actions, styled transcripts, approval
  cards, diff summaries, task context, queue context, and dock status footer.
- Add task exchange cards that summarize budget context, commands, raw prompts,
  raw outputs, provider decisions, and artifacts before showing raw markdown.
- Reuse the PTY/WebSocket/xterm.js terminal stack as provider-scoped terminal
  drawers inside the dock and as linked terminal/log context from task details.
- Keep backend scope additive: expose structured run, queue, terminal, approval,
  usage, and task projections without replacing current APIs.
- Add provider action descriptors for native dock/task actions, structured
  approval/diff summaries, unified status data, task exchange summaries, and
  command palette action descriptors.
- Do not add `.vsix` execution, VS Code extension hosting, vendor webview iframes,
  `vscode://` links, launch actions, or external VS Code controls.

Acceptance criteria:

- The Agent Dock gives Codex, Claude Code, Antigravity, and controller workflows
  a live VS Code-style panel experience inside CLITC.
- The Tasks tab gives the same workflows a durable VS Code-style history,
  approval, diff, retry, and final-report experience.
- Commands, logs, approvals, diffs, and queue blockers are summarized and styled
  by default, with raw details available behind expanders.
- Existing backend traffic control, task files, CLI execution, policy, approvals, and
  redaction remain authoritative.
- No feature requires VS Code to be installed or opened.

## Recommended Build Order

1. Durable run/event ledger.
2. Startup recovery.
3. State transition helpers.
4. Policy and approval service.
5. Provider adapters.
6. Typed decision parser.
7. SSE event stream.
8. Context builder.
9. Final reports and exports.
10. VS Code-style Agent Dock and Tasks tab.

This order fixes correctness and recovery before adding richer routing features.
