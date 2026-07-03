# Glossary

Project-specific terms for CLIT Controller IDE.

## Agent Dock

The right-hand live control center. It contains the controller transcript,
provider PTY tabs, terminal drawer, approvals, live run blocks, activity cards,
composer, and status footer.

## Agent Provider

One of the provider CLIs used for agent work: `codex`, `claude`, or
`antigravity`.

## Antigravity / `agy`

Google Antigravity CLI. It is the default QA provider. The app resolves both
`agy` and `antigravity` and also searches `~/.local/bin`.

## Approval

A durable request to authorize a risky action. Approvals live in
`<workspace>/.agentflow/approvals.json` and can be approved or rejected from the
UI.

## CLITC_RESULT_V1

The deterministic controller result protocol. A valid result block executes one
validated action. Invalid blocks mutate no state.

## Controller

The traffic-control agent that decides what happens next. The default controller
provider is `claude`.

## Event Bus

The in-process live stream in `backend/agentflow/event_bus.py`. Managed run
output, controller deltas, queue changes, task changes, approval updates, and
command lifecycle events flow through it.

## Headroom

Input-side context compression proxy for `claude` and `codex`. It is enabled by
default and fail-open.

## Legacy Directives

Older `agentflow-*` fenced blocks. They are still parsed as compatibility
fallback when no `CLITC_RESULT_V1` block is present.

## Live Run

A managed subprocess run whose stdout/stderr/controller text is streamed through
the event bus and accumulated by the frontend event store.

## Ponytail

Output-side prompt discipline injected into agent prompts. Levels are `off`,
`lite`, `full`, and `ultra`; default is `full`.

## Provider Terminal

A real PTY session for a provider, shown through xterm.js in Agent Dock. It uses
`/api/terminals/{provider}/ws`.

## Queue

The durable list of pending task steps in `<workspace>/.agentflow/queue.json`.
The dispatcher allows one active item per provider and preserves intra-task
ordering.

## Role

A routing slot such as controller, PM, engineer, or QA. Default routing:
controller `claude`, PM `codex`, engineer `claude`, QA `antigravity`.

## Run Ledger

Durable run metadata in `<workspace>/.agentflow/runs.json`. Full text output is
kept in run/task logs; the ledger stores metadata and tails.

## Task

A unit of work stored under `<workspace>/.agentflow/tasks/<task_id>/` with
`task.json`, markdown artifacts, exchanges, logs, events, and final state.

## Task Dispatch Map

The Tasks page provider-lane visualization for controller, Codex, Claude,
Antigravity, and local tools.

## Workspace

The selected project directory. Global state lives in `~/.agentflow/`; workspace
state lives in `<workspace>/.agentflow/`.
