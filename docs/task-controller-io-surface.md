# Task And Controller I/O Surface

CLIT Controller IDE should make task input and output feel like one coherent
system across the right-hand controller tab and the Tasks page. The controller
tab is the compact live surface. The Tasks page is the detailed review and audit
surface. They should share the same structure, typography, states, and display
model.

This surface model assumes
[Live Output Everywhere](./live-output-everywhere.md) as the final active-output
implementation. Live text appears as it is generated or received, and completed
task review is rebuilt from the same durable events.

This direction follows the deterministic workflow strategy in the attached
Gemini scheduler spec: the controller produces structured state, summaries, and
display models; the frontend renders those objects. The UI should not treat raw
agent prose or raw command logs as the primary product surface.

## Product Decision

Use a shared I/O model:

- **Input:** one consistent task composer pattern for controller prompts,
  task briefs, continuation prompts, approvals, retries, and reroutes.
- **Output:** one consistent transcript/card pattern for live output,
  summaries, status changes, commands, approvals, diffs, failures, and artifacts.
- **Detail depth:** right-hand controller tab is compact and live; Tasks page is
  detailed, paginated, searchable, and audit-friendly.
- **Raw data:** raw prompts, commands, JSON, directives, stdout, stderr, logs,
  and events are always available, but never the default reading experience.

## Deterministic Display Model

The controller should be treated like a workflow engine. It may use LLMs, but the
UI should render deterministic structured records.

Every meaningful controller/run result should be separable into three channels:

1. **Action Data**
   - Strict structured data.
   - No prose.
   - Examples: next action, tool name, task ID, provider, state transition,
     approval ID, queue item ID, artifact IDs.

2. **Human Summary**
   - Fixed, concise shape.
   - Maximum five bullets where possible.
   - Used in cards, task timeline, final reports, and read-aloud summaries.

3. **Display Data**
   - Structured UI model produced by the backend or frontend projection layer.
   - Examples: card type, badge, progress, current state, severity, primary
     action, related files, raw-detail links.

The frontend should render display data. It should not parse long freeform
agent output to decide basic UI state when structured state exists.

## Shared Visual Language

Both surfaces use the same primitives:

- provider marks
- step chips
- status badges
- compact command cards
- approval/diff cards
- live output blocks
- summary cards
- artifact chips
- paginated raw-detail drawers
- bottom status/footer rows

Typography:

- Body: `text-xs` or `text-[13px]`.
- Metadata: `text-[10px]` to `text-[11px]`.
- Section headers: existing `.section-title`.
- Monospace only for commands, paths, task IDs, provider IDs, model names,
  branches, JSON, directives, stdout, stderr, and logs.
- Do not use oversized text inside task cards or controller transcript rows.

## Right-Hand Controller Tab

The right-hand controller tab is the compact live command center.

Input composer:

- Single compact prompt box.
- Provider/controller selector when relevant.
- Traffic-control mode chip.
- Budget/health context chip.
- Attachment/context chips for selected files, tasks, references, or diffs.
- Icon buttons for send, stop, clear, terminal, command palette, mic dictation
  when local voice is available, and reference insertion when the reference tab
  is available.
- Drafts should stay editable until sent.
- Voice transcription must land in the prompt box for review before send.

Output:

- Live transcript rows for user prompts, controller summaries, provider replies,
  status changes, and queue events.
- The controller tab should show the current active state, not the whole task
  archive.
- Use compact cards for:
  - task created
  - queued step
  - run started
  - command output summary
  - approval required
  - diff available
  - failure/blocker
  - scheduled overflow
  - final status
- Raw detail is available through expanders or links to the Tasks page.
- Long running text uses smooth live output and auto-tail only while the user is
  at the bottom.

The controller tab should answer: "What is happening now, and what action can I
take next?"

## Tasks Page

The Tasks page is the detailed task console. It should be visually uniform with
the controller tab, but it can show more structure and history.

Input areas:

- Task continuation prompt uses the same composer pattern as the controller tab.
- Step-specific prompts should show selected step, provider, policy state,
  budget/health context, references, and expected action.
- Approval/retry/reroute inputs should be structured forms where possible rather
  than freeform text boxes.
- Raw directive entry, if exposed, must be advanced/debug-only.

Output areas:

- Default view is a human-readable timeline.
- Completed task output settles into summarized cards.
- Active task output still streams live using the same event store as the
  controller tab.
- Repeated budget context collapses into one compact row per run.
- Commands show status, provider, cwd, duration, and result first.
- Raw command text is behind an expander.
- Raw stdout/stderr/log/event/directive/JSON sections are paginated.
- Long diffs are summarized first and paginated by file or hunk.
- Final report appears as a concise summary with links to artifacts.

The Tasks page should answer: "What happened, why, what changed, and what can I
inspect or continue?"

## Output Card Taxonomy

Use a small fixed set of cards across both surfaces:

- `TASK_CREATED`
- `TASK_BRIEF`
- `STATE_TRANSITION`
- `QUEUE_ITEM`
- `RUN_STARTED`
- `RUN_OUTPUT`
- `COMMAND_RESULT`
- `APPROVAL_REQUIRED`
- `APPROVAL_RESOLVED`
- `DIFF_SUMMARY`
- `ARTIFACTS_CHANGED`
- `QA_STATUS`
- `FAILURE`
- `SCHEDULED_OVERFLOW`
- `FINAL_SUMMARY`
- `NEEDS_USER`

Each card should have:

- type
- title
- status/severity
- provider
- step
- task ID
- timestamp
- short human summary
- primary action
- secondary actions
- artifact links
- raw-detail links

## Raw Detail Pagination

Machine-readable data should use stable pagination, not one giant scrollback.

Paginated sections:

- raw prompt
- raw stdout
- raw stderr
- raw log
- structured events
- controller action data
- display data
- directive blocks
- JSON payloads
- long diffs

Pagination rules:

- default page size: small enough to keep the panel responsive
- preserve line numbers where possible
- allow copy page and copy all
- allow search/filter inside the raw section
- keep raw data read-only
- never remove the original artifact

## State And Validation Surface

The attached workflow strategy emphasizes finite state transitions. The UI should
make that visible without dumping implementation detail.

Show:

- current state
- previous state
- allowed next actions
- retry count
- failure policy when blocked
- validation status
- required approval
- generated artifacts
- run duration

Do not show:

- hidden reasoning
- raw JSON as the first view
- undocumented actions
- ambiguous "thinking" once a structured state is available

## Input/Output Alignment Rules

- Controller tab and Tasks page use the same card names and status labels.
- Controller tab cards are compact; Tasks page cards expand into detailed panels.
- Same provider/step/status chips render identically in both places.
- Same raw-detail component powers both expanders and paginated task panels.
- Same smooth streaming renderer powers active output in both places.
- Same approval cards and diff cards appear in both places, with more detail in
  Tasks.
- Same scheduling/overflow state appears in dock footer, task timeline, and
  queue filters.

## Acceptance Criteria

- The controller tab and Tasks page look like two densities of the same system.
- The Tasks page is more detailed without using larger or mismatched fonts.
- A user can understand a completed task without reading raw CLI output.
- A user can inspect every raw prompt, command, stdout, stderr, log, event, and
  directive through paginated read-only detail.
- The right-hand controller tab shows compact live state and clear next actions.
- Active output streams smoothly in both surfaces from the shared event store.
- Structured controller display data drives cards, badges, and statuses wherever
  available.
- No raw machine-readable block becomes the default reading experience.
