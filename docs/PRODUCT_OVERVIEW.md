# Product Overview

This page explains what Command Line Interface Traffic Controller (CLIT Controller
IDE, shortened to **CLITC**) is and how you use it, without requiring you to read
the code. For how it is built, see [Architecture](ARCHITECTURE.md); for how to run
and operate it, see [Operations](OPERATIONS.md); for the trust boundary, see
[Security](SECURITY.md). The interaction model and acceptance criteria live in
[Product Pillars](PILLARS.md).

## What it is

CLITC is a **local-first, single-user developer cockpit** that orchestrates the
command-line coding agents you already have installed — Claude Code, OpenAI Codex,
and Google Antigravity (`agy`/`antigravity`) — and runs them as subprocesses on your
own machine. Instead of bouncing between several terminals, chat windows, a file
tree, git diffs, and scattered task notes, you describe the work in one place, route
it to the right assistant, watch progress stream live, and review the result before
moving on.

It runs entirely on your machine: a FastAPI backend bound to `127.0.0.1:8787` and a
React web UI you open in a browser or install as a Chrome PWA. There is no login, no
database, and no cloud service (see [System boundaries](#system-boundaries)).

## Who it is for

The intended user is a **solo developer or designer who drives CLI coding agents**
and wants one cockpit to coordinate them. *(Inferred product intent:)* the framing
in the [README](../README.md) leans toward design-led, "vibe-coding" workflows where
one assistant plans, another implements, and a third reviews — but the underlying
machinery is general-purpose agent orchestration and works for any developer using
these CLIs.

CLITC assumes one person on one machine. It is explicitly **not** built for teams,
shared servers, or multi-tenant use.

## Problems it solves

Coordinating multiple AI coding assistants by hand gets messy fast. CLITC targets
the friction directly:

- **Token waste** — routes work intentionally so expensive assistants are saved for
  tasks that need them, and prefers diffs/file paths/task markdown over whole-file
  context.
- **Copy-paste fatigue** — keeps project context, task notes, logs, and hand-off
  files together instead of pasting them between chats and terminals.
- **Lost intent** — preserves the original request, routing decisions, approvals,
  and review history inside the workspace as durable files.
- **Slow, opaque review loops** — surfaces generated text, command output, changed
  files, and logs in one live view rather than waiting for a final result.
- **Terminal sprawl** — coordinates several agents (and real PTY terminals) from a
  single UI.

## Key concepts

Understanding these terms makes the rest of the product self-explanatory:

- **Workspace** — a project directory you point CLITC at. All state for that project
  lives under `<workspace>/.agentflow/` (tasks, events, queue, approvals, usage,
  chat). Switching workspaces switches the whole cockpit; data is never shared
  between workspaces.
- **Controller / orchestrator** — the conversational brain you chat with. It is not a
  hard-coded planner: it is one of your CLI agents (Antigravity by default) running
  with a traffic-control prompt. From plain chat it can create tasks, queue steps,
  run simple commands, mark work done, or ask you for input — by emitting fenced
  directive blocks that the system parses and acts on.
- **Providers** — the CLI tools CLITC drives: `claude` (implementation), `codex`
  (specs, plans, reviews), `antigravity`/`agy` (controller and QA), plus `git` and
  `gh`. Each keeps its own official login; CLITC never asks for or stores provider
  keys.
- **Tasks** — a unit of real work. Each task gets a folder with numbered markdown
  hand-off files (`00_USER_GOAL.md`, `01_CODEX_SPEC.md`,
  `04_CLAUDE_IMPLEMENTATION_SUMMARY.md`, etc.) plus structured state and an event
  timeline.
- **Steps** — the stages a task moves through, each routed to a role/provider:
  *Write Spec* → *Implement* → *QA / Test* → *Final Review* (with a *Fix Bugs* step
  available). Steps have an explicit state machine (queued, running, succeeded,
  failed, awaiting approval, skipped, and so on).
- **Queue** — the execution queue. The controller enqueues steps; the system runs
  one step per agent at a time, in order, and the queue survives restarts.
- **Approvals** — a durable gate. Risky-but-legitimate actions (e.g. `git push`,
  `npm install`, deploys) are not run automatically; they create an approval the user
  must grant. Outright dangerous commands are denied, not gated.
- **Live event stream** — the single source of operational truth. Every transition
  (chat delta, command output chunk, queue change, approval, failure, completion) is
  appended to a durable, cursor-resumable event ledger and streamed to the UI over
  SSE with a polling fallback, so every surface stays in sync.
- **Budget / routing mode** — Maximum Quality, Balanced, Budget Saver, or Manual
  Approval. Combined with per-provider usage health (green/yellow/red), this shapes
  which agent the controller routes to and whether commands need manual approval.

## Main workflow

The core loop:

1. **Pick a workspace.** Point CLITC at a project directory in the Explorer/Projects
   view. You see its file tree, git status, and diffs.
2. **Chat with the controller.** Describe what you want in the chat dock. The
   controller replies as prose and, when appropriate, decides to act.
3. **It creates and queues tasks.** From the conversation the controller can open a
   task (writing your goal to `00_USER_GOAL.md`) and queue the steps to run — either
   the full Spec → Implement → QA → Review chain or a specific subset.
4. **Agents run as steps.** The queue cues each agent in turn. A step spawns the
   routed CLI (e.g. Codex to write the spec, Claude to implement), which reads the
   prior hand-off files and writes its own.
5. **You watch live output and handle approvals.** Generated text and command output
   stream in as they are produced — no waiting for the process to exit. If a step
   hits a gated command, it pauses and asks for approval; you approve or reject in
   place. After a step finishes, the system can consult the controller for what to do
   next.
6. **You review.** The task detail view shows summaries, changed files, checks,
   approvals, failures, and decisions first; raw prompts, stdout/stderr, and logs are
   available behind expanders. You can retry, skip, reroute, approve, run the next
   step, or continue the work.

Alongside this orchestrated loop, you can talk to any single provider directly, run
real PTY terminals, browse and edit files, view a live preview of the workspace's
frontend, and track approximate provider usage.

## User-visible capabilities

The UI is organized into views (exact labels may vary):

- **Explorer / Projects** — workspace picker, file tree, source-control panel (status
  and diffs), a tabbed code reader/editor, and an output/log panel.
- **Chat dock (Agent Dock)** — the controller conversation plus per-provider tabs
  (`controller`, `codex`, `claude`, `antigravity`), live streaming transcript,
  command/approval/diff cards, and a provider-scoped terminal drawer.
- **Tasks** — split list/detail review surface: task queue, flow board, step chat,
  conversation replay, structured I/O cards, and continuation actions (retry, skip,
  reroute, approve/reject, run next, open log/task file, copy command, stop).
- **Agents** — connected-assistant status, version/login detection, and UI
  install/setup actions for supported CLIs.
- **Terminals** — standalone PTY terminals over WebSockets, themed with xterm.
- **Preview** — embedded browser for the workspace's frontend; CLITC can start the
  dev server for you.
- **Usage** — approximate per-provider usage and health (green/yellow/red) feeding
  routing decisions.
- **Logs / Settings** — run logs and configuration (including the budget/routing
  mode).

## System boundaries

- **Local and loopback-only.** The backend binds `127.0.0.1`; there is **no auth by
  design** because it is single-user on your machine. Origin/CSRF/WebSocket guards
  exist to keep it that way.
- **No database.** All state is plaintext JSON written atomically — global config
  under `~/.agentflow/` and per-workspace state under `<workspace>/.agentflow/`. The
  event ledger is cursor-resumable, and the app recovers in-flight state on startup.
- **It drives your CLIs; it doesn't replace them.** CLITC spawns the official `claude`
  / `codex` / `antigravity` binaries you installed and logged into. It stores no
  provider credentials.
- **Command execution is policed.** Direct execution is exec-only and
  workspace-confined; dangerous commands are denied and risky ones require explicit,
  durable approval.

## Explicit non-goals

- **Not a VS Code clone or extension host.** The Tasks and dock surfaces deliberately
  echo VS Code-style review/diff/approval patterns, but CLITC must never depend on
  VS Code APIs, `vscode://` deep links, or `.vsix`/vendor plugin execution.
- **Not multi-user.** No accounts, roles, tenancy, or sharing.
- **Not a cloud service.** It is a local process you run yourself; nothing is hosted.
- **Not a reference importer that edits your code silently.** The planned UI/UX
  reference library guides generated work but does not overwrite code without a normal
  task → diff → approval path.

## Maturity

CLITC is in **beta**. The orchestration loop, live event streaming, task/step/queue
state machines, approvals, provider detection, terminals, file/diff browsing, and the
deterministic output contracts are implemented and exercised by tests. The five
product pillars in [Product Pillars](PILLARS.md) document what is fully implemented
(✅) versus partial (◐); notable partials include surfacing token/latency metrics as a
dashboard, full ANSI/CLI normalization beyond escape stripping, and consolidating
auto-scroll across every legacy surface.

## Known mocked or incomplete experiences

- **Token-efficiency savings** are reported only when actually measured; unmeasured
  values are `null`, never fabricated. The Headroom context-optimization proxy
  (token-saving) is **optional and off by default** — when disabled or unreachable,
  agents run directly with no change to behavior.
- **Local voice I/O** (dictation and spoken summaries via MLX Parakeet / mlx-swift
  TTS) is **designed but not yet implemented** — it is on the roadmap, not in the
  running app.
- **Usage tracking is approximate**, derived from estimated prompt/output sizes and
  call counts rather than billed numbers from the providers.
- **The UI/UX reference library** and a polished standalone app-mode launcher are
  roadmap items described in [DESIGN.md](../DESIGN.md) and the
  [README](../README.md), not finished features.
