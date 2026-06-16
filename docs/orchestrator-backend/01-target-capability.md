# Target Capability

The controller backend is complete when a user can describe work once, then let
Command Line Interface Terminal Controller (CLIT Controller IDE) route, execute,
verify, recover, and report the task without manually juggling CLIs or losing
control of risky operations.

## End-To-End User Flow

1. The user selects a workspace.
2. The backend initializes `.agentflow/` and loads routing, usage, provider, queue,
   task, and run state.
3. The user asks the controller for work.
4. The controller either answers directly, creates a task, queues agent steps, or
   runs a safe local command.
5. The dispatcher executes eligible work in order, with one active run per provider.
6. Each run writes prompt, output, logs, artifacts, state transitions, usage, and a
   human-readable timeline event.
7. After each controlled step, the controller receives the actual task state and
   decides the next action.
8. The loop ends with a durable `done`, `needs_user`, `failed`, or `cancelled` verdict.
9. The user can restart the backend and still see accurate task, queue, log, and run
   state.

## Functional Requirements

### Workspace

- Open one active workspace at a time.
- Create and maintain `<workspace>/.agentflow/`.
- Never preview or leak sensitive files such as `.env`.
- Keep generated CLITC files out of the user's repository by default.
- Confine all automated commands to the selected workspace unless the user explicitly
  approves a shared-resource action.

### Provider Management

- Detect installed providers and their executable paths.
- Track provider roles: controller, PM, engineer, QA, local tools, optional local LLMs.
- Support configurable command templates and model selections.
- Keep provider-specific CLI syntax outside traffic-control logic.
- Expose install and login helpers without storing API keys, passwords, or tokens.
- Report provider availability, auth hints, model options, and usage health in a
  stable shape.

### Task Model

- Create a task with stable ID, title, goal, status, events, steps, and artifacts.
- Maintain the existing markdown handoff files:
  - `00_USER_GOAL.md`
  - `01_CODEX_SPEC.md`
  - `02_CODEX_IMPLEMENTATION_PLAN.md`
  - `03_CLAUDE_PROMPT.md`
  - `04_CLAUDE_IMPLEMENTATION_SUMMARY.md`
  - `05_QA_RESULTS.md`
  - `06_BUGS_FOR_CLAUDE.md`
  - `07_CODEX_FINAL_REVIEW.md`
  - `ROUTING_DECISIONS.md`
- Support fixed pipeline steps and dynamic next-step decisions.
- Record which artifacts and production files changed after every agent run.
- Represent terminal task outcomes explicitly: `done`, `needs_user`, `failed`,
  `cancelled`, and `abandoned`.

### Traffic Control

- Accept structured decisions from the controller:
  - create task
  - queue steps
  - run safe local command
  - declare done
  - request user input
  - retry or reroute after failure
- Validate every decision before mutation.
- Prevent duplicate active work for the same task/step.
- Preserve intra-task order.
- Enforce one active run per provider.
- Consult the controller after every controlled step, with bounded consult loops.
- Allow manual approval mode where automatic execution becomes preview-only.

### Execution

- Start subprocesses without shell interpolation.
- Capture stdout and stderr with redaction.
- Write durable prompt and log files per run.
- Cancel one run or all active runs.
- Recover accurately after backend restart.
- Distinguish provider missing, auth failure, command failure, timeout, cancellation,
  validation denial, and backend error.
- Support long-running local commands such as dev servers without blocking the queue.

### Policy And Approval

- Automatically allow low-risk local reads/checks inside the workspace.
- Require approval for shared-resource or remote-state changes such as installs,
  login launches, `git push`, `git pull`, package publishing, cloud deploys, and
  commands outside the workspace.
- Deny shell operators, path traversal, and destructive commands unless represented
  by explicit, reviewed backend actions.
- Log every approval decision and policy denial.

### Observability

- Show current queue, running providers, task events, logs, prompt/output exchanges,
  provider usage, and final verdict.
- Add streaming events for logs and queue/task state updates.
- Keep polling endpoints as a fallback.
- Make every automatic decision inspectable from task files or structured events.

## Non-Goals

- Hosted traffic-control service.
- Storing API keys or provider tokens.
- Replacing provider CLIs with direct provider APIs.
- Multi-user team synchronization in the first full backend milestone.
- Browser-based verification as a required backend capability.

## Success Criteria

- A task can be created, planned, implemented, checked, reviewed, and declared done
  without manual CLI copying.
- Restarting the backend during queued, running, blocked, and completed states does
  not corrupt state or hide the true outcome.
- Missing providers, failed commands, manual approval mode, and red-Claude routing
  all produce useful, durable states rather than silent failures.
- The frontend can render task, queue, run, log, and usage state from stable API
  responses without reconstructing backend logic.
