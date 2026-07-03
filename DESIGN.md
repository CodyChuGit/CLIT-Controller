# CLIT Controller IDE Design Language

The app should feel like a compact IDE surface: dense, quiet, rectangular, and
built for repeated work.

## Principles

- Use panels, borders, and section headers instead of floating marketing cards.
- Keep information dense but scannable.
- Use color for state, not decoration.
- Use monospace for provider ids, task ids, paths, commands, branches, and model
  names.
- Show raw output only when it helps inspection; structured summaries and cards
  should lead.
- Keep Agent Dock and Tasks visually related: compact live view on the right,
  detailed review view in Tasks.

## Naming

- Product: CLIT Controller IDE.
- Full descriptive name: Command Line Interface Terminal Controller.
- Tagline: Vibe with CLIT Controller.
- Short names after first mention: CLIT Controller or CLITC.

## Layout

Current shell:

- left activity bar
- main page content
- right-hand Agent Dock
- bottom status bar

Current pages:

- Projects
- Agents
- Tasks
- Preview
- Usage
- Logs
- Settings

There is no standalone Terminals page. Provider terminals live in Agent Dock.

## Agent Dock

Agent Dock is the right-hand live control center.

Required behavior:

- controller tab for traffic-control chat
- provider tabs for `codex`, `claude`, and `antigravity`
- real PTY output in provider tabs
- terminal drawer for the selected controller provider
- live managed output from the shared event store
- compact activity cards for tasks, queue, commands, approvals, failures, and
  completions
- composer with context chips and clear destination
- footer with workspace, provider, queue, run, and health state

Completed text renders statically. Active generated text may be smoothed for
readability, but it must be based on real live deltas, not cached final text.

## Tasks

Tasks is the durable review and distribution surface.

Required behavior:

- provider-lane dispatch map for Controller, Codex, Claude, Antigravity, and
  local tools
- queue controls for retry, skip, reroute, remove, approve, and reject
- task detail with prompts, outputs, logs, events, files, artifacts, and changed
  files
- live selected-task output from the shared event store
- raw detail behind tabs, expanders, or paginated views

The Tasks page explains how work moved through the agentic flow; it should not
look like a generic chat transcript.

## Components

- Buttons: icon buttons for common tools, text buttons for clear commands and
  approval actions.
- Cards: only for repeated items, modals, and framed tool results; do not nest
  cards.
- Tabs: use for provider/task/raw-detail views.
- Badges: include text, not color alone.
- Terminal: xterm.js surface with visible disconnected, missing, launching,
  ready, and closed states.

## Motion

Use short, functional transitions. Respect reduced motion. Do not animate
history as though it were being generated live.

## Accessibility

- All icon buttons need `title` and `aria-label`.
- Focus states must remain visible.
- State cannot be color-only.
- Text must fit in compact controls at desktop and mobile widths.
