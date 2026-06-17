# Phase 1.5 Product Workbench

This phase sits between the durable run/event ledger and explicit state
machines. The goal is to make CLIT Controller IDE more useful before deeper
backend refactors: task output becomes readable, frontend styling gets a
reference database, and overflow work can be scheduled instead of abandoned when
limits are reached.

## Goals

- Make task output human-readable by default.
- Put machine-readable prompt, command, log, JSON, stdout, and stderr data behind
  paginated drill-down views.
- Add a UI/UX reference-library right-hand tab for fast frontend style swaps.
- Add a reference-library extraction tool that builds a local database from
  component libraries and design examples.
- Integrate overflow work with the TestApp Calendar Scheduler so user-limit and
  weekly-limit tasks can resume later.
- Add optional local voice I/O with MLX Parakeet STT and
  `mlx-swift-dots-tts` TTS.
- Identify additional CLI IDE features that fit CLITC's local-first traffic
  control model.

## Task Output View Rework

The current Tasks tab still exposes too much raw output. It should become a
review surface first and a raw artifact browser second.

Use [Task And Controller I/O Surface](./task-controller-io-surface.md) as the
source of truth for shared styling between the right-hand controller tab and the
Tasks page. The controller tab is the compact live surface; the Tasks page is the
more detailed review surface.

Requirements:

- Default view shows human-readable summaries, not raw markdown or raw CLI logs.
- Task input and continuation controls match the right-hand controller composer:
  compact prompt area, traffic-control context, provider/step chips, budget/health
  state, attachments/references, and icon-first actions.
- Font sizing matches the rest of the IDE: `text-xs` or `text-[13px]` for body
  rows, `text-[10px]` to `text-[11px]` for metadata, and monospace only for
  commands, paths, task IDs, provider IDs, model names, branches, and raw output.
- Prompt/output exchanges render as compact cards:
  - task brief
  - provider
  - step
  - status
  - elapsed time
  - files changed
  - tests/checks detected
  - approval or failure reason
  - short human summary
- Repeated budget context is collapsed into one summary row per exchange or run.
- Commands are summarized first with status, cwd, provider, and duration; full
  command text is available in an expander.
- Machine-readable sections are paginated:
  - raw prompt
  - raw stdout
  - raw stderr
  - raw log
  - structured events
  - directive blocks
  - JSON payloads
  - long diffs
- Pagination should use stable slices with page size controls, not giant
  scrollback panes.
- Active runs still stream progressive text, but completed runs settle into the
  summarized replay view.
- Raw detail remains available for audit and copying, but it is never the first
  thing the user has to read.
- Controller/action data, human summaries, and display data stay separate so the
  UI renders structured state instead of parsing raw prose.

Suggested task-detail layout:

- **Timeline:** human-readable run cards and continuation controls.
- **Summary:** final report, detected files, checks, failures, and decisions.
- **Output:** summarized stdout/stderr with paginated raw views.
- **Commands:** command cards with status and expandable raw commands.
- **Artifacts:** task markdown, diffs, changed files, logs, approvals, and routing
  decisions.
- **Events:** paginated durable events for debugging.

Acceptance criteria:

- The default task detail view can be understood without reading raw CLI output.
- Raw prompt/log/stdout/stderr sections are paginated and expandable.
- Font sizes match the rest of the IDE.
- Repeated budget context no longer dominates the output view.
- The Tasks page and right-hand controller tab look like two densities of the
  same I/O system.
- Users can still reach every original artifact and raw machine-readable record.

## UI/UX Reference Library Tab

Add a dedicated right-hand tab for frontend reference material. This is separate
from provider chat tabs. Its job is to help CLITC build and restyle frontends
quickly using reusable local references.

Target UX:

- Right-hand tab named **References** or **UI Ref**.
- Dense searchable library of design systems, components, patterns, and style
  recipes.
- Filters for stack, framework, component type, density, color system, typography,
  interaction pattern, accessibility notes, and license/source.
- Preview pane for component examples and extracted variants.
- Actions:
  - add reference source
  - extract library
  - tag components
  - create style recipe
  - apply style recipe to selected frontend files
  - copy implementation prompt
  - queue style-swap task
- Components are references, not uncontrolled code imports. Applying a reference
  still goes through task, diff, and approval workflows.

Reference database should support:

- component name
- source path or URL
- framework
- dependencies
- props/API shape
- style tokens
- Tailwind classes or CSS variables
- states and variants
- accessibility notes
- screenshots or preview thumbnails when available
- example code snippets
- license/source metadata
- tags
- extracted date
- modified/reference version

## Reference Extraction Tool

Build a local extraction tool that turns component libraries into a searchable
reference database for future frontend work.

Inputs:

- local React/TypeScript component directories
- local CSS/Tailwind/token files
- Storybook stories when present
- shadcn-style component registries when present
- local markdown docs and examples
- explicitly approved external sources in a future pass

Outputs:

- normalized JSON records under `.agentflow/references/`
- readable markdown summaries
- optional preview assets when available
- source/license metadata
- modification notes for adapted references

Extraction behavior:

- Prefer structured parsing for TypeScript/TSX, JSON, CSS, and package metadata.
- Detect component names, exports, props, variants, dependencies, tokens, class
  patterns, and common states.
- Preserve license and source attribution.
- Never overwrite user component files during extraction.
- Treat generated/adapted reference components as separate artifacts with clear
  provenance.
- Keep the database local to the workspace unless the user explicitly exports it.

Acceptance criteria:

- A user can extract a local component library into searchable reference records.
- The right-hand reference tab can browse and filter extracted records.
- A style-swap task can include selected references without pasting entire
  libraries into prompts.
- Applying references produces normal task artifacts and diffs, not silent file
  changes.

## TestApp Calendar Scheduler Integration

When provider/user/weekly limits are reached, CLITC should not lose the task or
force the user to manually remember it. Overflow work should be scheduled with
the TestApp Calendar Scheduler and resumed when limits reset or a scheduled
window arrives.

Overflow triggers:

- provider health set to red
- known user limit reached
- known weekly limit reached
- manual "run later" action
- budget mode refuses a high-cost step
- queue policy defers non-urgent work

Scheduled item fields:

- task ID
- queue item ID
- provider
- step
- reason: `user_limit`, `weekly_limit`, `provider_unavailable`,
  `budget_deferred`, or `manual_delay`
- earliest run time
- preferred time window
- estimated duration
- saved prompt/context snapshot
- resume action
- approval requirement
- status
- scheduler external ID

Backend behavior:

- Add an overflow queue state without marking the task failed.
- Create a scheduler handoff record before sending anything to TestApp.
- Send only the minimum scheduling metadata needed by TestApp.
- Keep prompts, logs, and task artifacts inside CLITC unless explicitly approved.
- Reconcile scheduled items on startup.
- Resume eligible work through the normal queue and approval system.
- If TestApp is unavailable, keep the overflow item locally and show a clear
  state in the Tasks tab and status bar.

Frontend behavior:

- Show overflow tasks in the Tasks tab with reason and scheduled time.
- Add filters for active, blocked, overflow, scheduled, and completed.
- Add actions: schedule, reschedule, run now, cancel scheduled run, and copy
  scheduler details.
- Show schedule state in the right-hand dock/status footer when relevant.

Acceptance criteria:

- Reaching a user or weekly limit produces a scheduled overflow item instead of a
  failed or forgotten task.
- Scheduled work resumes through normal CLITC traffic control.
- The user can see why the task was delayed and when it will run.
- No remote scheduling state is changed without a user-approved scheduler
  integration.

## Local Voice I/O

Voice should become a local optional interface for starting work and reviewing
status without sending audio to hosted services. See
[Local Voice I/O](./local-voice-io.md).

Target backends:

- STT: MLX Parakeet for local speech-to-text on Apple/MLX-capable machines.
- TTS: `mlx-swift-dots-tts` for local text-to-speech on Apple/MLX-capable
  machines.

Requirements:

- Push-to-talk only in the first pass.
- Transcribed text lands in the prompt box for user review before sending.
- Voice-generated prompts follow the same task, queue, approval, and policy rules
  as typed prompts.
- TTS reads concise summaries, final reports, overflow notices, and selected run
  status, not raw logs by default.
- Missing local voice providers show availability/setup state without blocking
  the rest of CLITC.
- No cloud STT/TTS provider, always-on mic, wake word, or raw audio retention by
  default.

Acceptance criteria:

- A user can dictate a prompt locally, review/edit the transcript, and send it.
- A user can play and stop a local spoken task/run summary.
- Voice actions produce durable events and never bypass written approvals.
- Audio stays local and temporary unless the user explicitly enables retention.

## Additional CLI IDE Feature Candidates

These are good fits for CLITC. They should be evaluated after Phase 1.5 scope is
stable.

- **Workspace Checkpoints:** create local snapshots before agent edits so the
  user can inspect or restore a task-level checkpoint without touching unrelated
  work.
- **Command Recipes:** save approved local command sequences as reusable recipes
  with policy metadata, expected outputs, and rollback notes.
- **Environment Doctor:** diagnose missing CLIs, broken auth, old runtimes, bad
  npm caches, Python version issues, and workspace permission problems.
- **Quota Planner:** show provider health, estimated run cost, deferred work, and
  next safe execution windows in one compact panel.
- **Diff Approval Workbench:** group changed files by task/run, summarize risk,
  show tests linked to diffs, and approve or reject changes by file.
- **Test Intelligence:** parse common test outputs, group failures, detect flaky
  retries, and create focused fix prompts.
- **Prompt Inspector:** show exactly what context went into a run, why it was
  selected, and what was omitted for budget.
- **Repro Capsule:** export a task's prompts, logs, events, diffs, environment
  summary, and final report into one local diagnostic bundle.
- **Workspace Profiles:** save per-project provider preferences, command
  templates, budget mode, ignored paths, and scheduler policy.
- **Voice Handoff Expansion:** after the first local voice pass, consider richer
  dictation editing, summary playlists, and hands-free status checks while still
  keeping push-to-talk and written approvals as the default safety posture.

## Non-Goals

- No hosted reference database.
- No silent style rewrites outside task/diff workflows.
- No automatic remote scheduling changes without approval.
- No cloud voice processing.
- No always-on microphone capture.
- No raw output removal; raw records remain available through pagination.
- No replacement of the existing task/event/queue architecture.
