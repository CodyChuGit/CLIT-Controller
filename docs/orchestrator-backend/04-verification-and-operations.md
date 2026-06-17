# Verification And Operations

The backend is only fully functional if traffic control can be trusted under failure,
restart, missing-provider, and approval-heavy conditions. This document defines the
verification matrix and operational checks.

## Test Strategy

Use the smallest reliable checks for each layer.

### Unit Tests

Cover pure logic and local state transitions:

- Directive parsing.
- Command policy classification.
- Task output summarization and pagination helpers.
- Task/controller display projection helpers.
- Reference extraction normalization.
- Overflow scheduling state classification.
- Voice provider detection and local-only policy checks.
- Provider adapter command rendering.
- Redaction.
- Usage window resets.
- Routing recommendations.
- Task, step, queue, run, and approval state transitions.
- Failure classification.
- Safe path resolution.

### Service Tests

Use temporary workspaces and fake providers:

- Create workspace.
- Create task.
- Queue steps.
- Dispatch fake provider command.
- Capture prompt and log files.
- Mark run succeeded, failed, cancelled, provider missing, and policy denied.
- Consult controller with fake output.
- Retry, skip, reroute, approve, and reject.
- Recover after simulated backend restart.

Fake providers should be tiny executable scripts checked into tests or generated in
temporary directories. They should simulate:

- success with stdout
- non-zero exit
- slow run
- auth failure output
- large output
- artifact writes
- very verbose stdout/stderr
- repeated budget context blocks

### API Tests

Use FastAPI test clients:

- Workspace endpoints.
- Agent list/check endpoints with mocked provider registry.
- Task detail endpoint before and after runs.
- Task detail summary and paginated raw output endpoints or response sections.
- Task/controller display projections for compact dock cards and detailed task
  cards.
- Queue add/approve/remove/clear/retry/skip endpoints.
- Chat send/direct endpoints with fake controller decisions.
- Logs and events endpoints.
- Approval endpoints.
- Reference-library browse/search/detail endpoints when introduced.
- Scheduler overflow handoff/status endpoints when introduced.
- Voice availability, STT, TTS, and stop endpoints when introduced.

### Recovery Tests

Simulate restart by clearing in-memory runner state and reloading persisted state.

Required scenarios:

- Queue item was `queued`.
- Queue item was `awaiting_approval`.
- Queue item was `running` and process is gone.
- Queue item was `running` and log file has terminal status.
- Run record exists but queue item is missing.
- Task step says `running` but no matching run exists.
- Controller consult was pending.
- Approval was pending.

Expected result:

- No stale `running` state remains unless the process is actually reattached.
- Recovery appends explicit events.
- Later queue items are blocked or made eligible according to clear rules.

### Safety Tests

Policy tests should verify:

- Shell operators are denied.
- Path traversal is denied.
- Absolute paths outside the workspace are denied.
- Remote Git operations require approval.
- Installs require approval.
- Safe local checks are allowed.
- Manual approval mode turns auto-dispatch into approval holds.
- Denied commands are never passed to the subprocess runner.

### Regression Tests For Existing Behavior

Keep coverage for current beta behavior:

- `agentflow-task` creates markdown handoff files.
- `agentflow-queue` queues valid step IDs and rejects invalid ones.
- `agentflow-run` accepts only plain commands.
- Provider missing saves intended prompt to task logs.
- Red-Claude implementation requires confirmation.
- Budget Saver can skip small-task spec steps.
- Prompt/output exchanges can be rebuilt from task logs.

## Acceptance Workflow Matrix

| Scenario | Expected outcome |
|---|---|
| User asks for a simple local command | Backend runs safe command directly and reports result |
| User asks for a feature | Controller creates task and queues appropriate first step |
| Provider executable is missing | Step becomes `provider_missing`, prompt is saved, queue continues or blocks according to policy |
| Claude health is red | Implementation step requires explicit approval |
| Manual Approval mode is enabled | Queue items become approval holds, no automatic process starts |
| Agent step fails | Later steps for same task block; user can retry, skip, or reroute |
| Backend restarts mid-run | State recovers to truthful terminal or blocked status |
| Controller emits invalid directive | Task records parse/validation error and requests user input |
| Controller says done | Task gets durable final verdict and final event |
| User cancels run | Process group is terminated, run and queue item become `cancelled` |
| Task has very large raw output | UI/API exposes readable summary first and paginated raw details |
| Controller and Tasks show same run | Dock renders compact card and Tasks renders detailed card from same projection |
| User extracts a local component library | Reference records are created without modifying source files |
| Provider/user weekly limit is reached | Queue item becomes overflow/scheduled instead of failed |
| TestApp Scheduler is unavailable | Overflow item stays local with visible retry/reschedule state |
| User dictates a prompt | Transcript appears for review before sending |
| User plays a task summary | Local TTS starts and can be stopped without changing task state |

## Operational Requirements

### Logging

- Redact secrets before storing or returning output.
- Keep prompt files and logs per task run.
- Keep a bounded global activity log for UI speed.
- Store full durable event history per workspace.
- Include command preview, cwd, provider, task, step, exit code, duration, and failure
  kind for every run.

### Metrics

Track locally:

- Runs by provider and status.
- Average run duration by provider and step.
- Queue wait time.
- Approval wait time.
- Provider missing/auth failure counts.
- Estimated prompt and output characters.
- Expensive calls avoided.
- Local steps completed.
- Overflow tasks scheduled, resumed, cancelled, and kept local.
- Reference extraction counts by source and framework.
- Local STT/TTS availability, failures, and run duration.

### Health Checks

Expose:

- Backend health.
- Current workspace readiness.
- Dispatcher status.
- Durable store status.
- Provider availability snapshot age.
- Active run count.
- Event stream health.

### Data Retention

Defaults:

- Keep all task markdown files.
- Keep all run prompt/log files inside task folders.
- Bound in-memory output tails.
- Keep full raw task records even when UI defaults to summaries and pagination.
- Keep reference-library records local to the workspace unless explicitly exported.
- Keep scheduler handoff records for overflow audit and resume.
- Do not retain raw voice audio by default; keep only explicit transcript/task
  records and voice event metadata.
- Add a cleanup command later for old task logs, but never silently delete task
  artifacts.

### Migration

Every persisted schema should have:

- `schemaVersion`
- forward migration on load
- best-effort backup before destructive migration
- clear recovery event if migration changes live queue/run state

## Definition Of Done For The Full Backend

- All roadmap phases through policy, typed decisions, recovery, and streaming events
  are implemented.
- The acceptance workflow matrix passes with fake providers.
- Restart recovery tests pass.
- Safety tests prove denied commands do not execute.
- Existing frontend endpoints remain compatible or are intentionally versioned.
- Task folders remain readable and useful without the UI.
- The final task report explains what the controller decided, what agents ran, what
  changed, what failed or was skipped, and why the task is done or needs the user.
- Phase 1.5 product workbench checks pass: task summaries are readable, raw output
  is paginated, reference extraction is local and auditable, and overflow schedule
  state resumes through normal traffic control.
- Task/controller I/O checks pass: action data, human summaries, and display data
  stay separate, and raw agent prose is not required for basic UI state.
- Local voice checks pass when providers are available and degrade cleanly when
  MLX Parakeet or `mlx-swift-dots-tts` is missing.
