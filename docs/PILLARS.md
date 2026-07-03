# Product Pillars

These are the current product guarantees for CLIT Controller IDE.

## 1. Local-First CLI Orchestration

The app is a UI for user-installed CLI tools. It does not host models or store
provider credentials. Provider auth remains with each CLI.

Default roles:

- controller: `claude`
- PM: `codex`
- engineer: `claude`
- QA: `antigravity`

## 2. Live Output From One Event Stream

Managed output appears while it is generated. Controller replies, provider chat,
task runs, command output, queue changes, approvals, failures, and completions
flow through one workspace event stream.

Frontend surfaces consume that shared stream:

- Agent Dock transcript and live run blocks
- Tasks live step output
- Logs active run tails
- status/footer indicators

Interactive provider tabs are separate PTY terminals, but their lifecycle is
still visible through diagnostics and UI state.

## 3. Deterministic Controller Actions

Controller state changes use `CLITC_RESULT_V1`.

Guarantees:

- the action union is explicit
- one valid result executes one action
- invalid result blocks mutate no state
- legacy directives are fallback only
- command actions still pass policy and approval gates

## 4. Reviewable Task Distribution

Tasks are shown by provider lane so non-terminal users can see how work is being
distributed:

- Controller: decisions and consults
- Codex: specs, plans, reviews
- Claude: implementation and fixes
- Antigravity: QA and broad checks
- Local tools: commands, git, tests, preview

Raw prompts, logs, events, outputs, changed files, and artifacts remain
available for review.

## 5. Safety And Recovery

The app is local and single-user, but still enforces guardrails:

- localhost binding
- local origin checks for mutating requests and terminal sockets
- workspace path confinement
- argv-based subprocess execution
- command policy and approvals
- redaction before persistence or broadcast
- startup recovery for stale runs, queue items, and task steps
- PTY orphan cleanup

## 6. Token Discipline

Headroom handles input-side compression for `claude` and `codex`. It is enabled
by default and fail-open.

Ponytail handles output-side prompt discipline. It defaults to `full` and can be
changed in Settings.
