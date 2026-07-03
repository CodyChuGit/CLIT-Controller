# Product Overview

CLIT Controller IDE is a local-first UI for people who use CLI coding agents.
It gives non-terminal users a readable way to route work, watch it stream live,
review changes, and continue tasks without juggling several shells.

## Core Idea

The app does not host models and does not replace official provider CLIs. It
uses the tools already installed on the user's machine:

- `claude` for the default controller and implementation work
- `codex` for specs, plans, and reviews
- `agy` / `antigravity` for QA, broad checks, and terminal investigation
- `git`, shell commands, and local dev servers for workspace operations

The backend is the traffic-control boundary. It validates controller actions,
checks policy, gates risky commands behind approvals, confines paths to the
workspace, redacts secrets, and streams events to the UI.

## Main Surfaces

### Explorer

The Explorer page is the workspace surface:

- choose the active workspace
- browse files
- open editor tabs
- view git status and diffs
- stage, unstage, and commit local changes

Generated app state lives under `<workspace>/.agentflow/`; provider auth stays
with the providers' own CLIs.

### Agent Dock

The right-hand Agent Dock is the live command center.

- `controller` tab: asks the controller to plan, create tasks, queue steps, run
  safe commands, or request approvals.
- provider tabs: real PTY terminals for `codex`, `claude`, and `antigravity`.
- terminal drawer: a real PTY for the selected controller engine.
- transcript: completed messages render statically; active output streams from
  the shared event store.
- activity cards: queue, task, command, approval, and controller events are
  shown as compact cards.

### Tasks

The Tasks page is the detailed review and distribution workbench.

It lays a task out by provider lane:

- Controller: routing decisions, consults, approvals, final verdicts
- Codex: spec, plan, and review work
- Claude: implementation and fixes
- Antigravity: QA and broad checks
- Local tools: shell, git, tests, preview commands

Each task also keeps raw prompts, outputs, logs, events, artifacts, changed
files, and final summaries for audit and recovery.

### Agents

The Agents page detects and manages CLI tools:

- git
- GitHub CLI
- Codex CLI
- Claude Code
- Google Antigravity CLI
- optional local model tools such as Ollama and MLX entry points

Agent install and login helpers call the official tools. CLIT Controller does
not store provider credentials.

### Usage And Settings

Usage tracks local counters, manual provider health, and live quota where a CLI
exposes it. Settings owns routing defaults, command templates, model choices,
Headroom input compression, and Ponytail output discipline.

## Controller Protocol

Controller replies can include human-readable text, but state changes are driven
by the deterministic `CLITC_RESULT_V1` block. The backend parses and validates
that block before mutating anything.

Supported controller actions include:

- answer
- create task
- queue steps
- run command
- request approval
- request user input
- retry
- reroute
- complete task
- cancel

Legacy `agentflow-*` blocks are still supported as a compatibility fallback only
when no `CLITC_RESULT_V1` block is present.

## Live Output

There is one workspace event stream:

- SSE: `GET /api/events/stream`
- polling fallback: `GET /api/events?cursor=<id>`

Provider chat, controller output, task runs, command output, queue changes,
approvals, failures, cancellations, and final states all flow through that
stream. The frontend's `SmoothStreamingText` component only smooths display; it
does not own network or chat state.

Interactive provider terminals are separate real PTY sessions over WebSocket:
`/api/terminals/{provider}/ws`.

## Safety Model

CLIT Controller is intentionally local and single-user:

- binds to localhost
- rejects foreign browser origins for mutating requests and terminal sockets
- confines file operations to the selected workspace
- starts subprocesses without `shell=True`
- redacts secrets before persistence or broadcast
- requires approval for risky commands such as installs, deploys, and remote git
  operations
- recovers durable state after restart

## Token Controls

Headroom is the input-side token compression library, applied in-process to the prompts CLIT Controller builds.
It is enabled by default and fail-open.

Ponytail is the output-side prompt discipline that pushes agents toward smaller,
shorter, more local changes. It defaults to `full` and is configurable in
Settings.
