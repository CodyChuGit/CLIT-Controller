# Frontend Reference

The frontend is a React 18 + Vite + TypeScript app styled with Tailwind. It is
the local cockpit for files, agents, tasks, preview, usage, logs, settings, and
the right-hand Agent Dock.

## App Shell

`frontend/src/App.tsx` owns:

- active page
- current workspace
- git/usage/queue status for the shell
- editor tabs and unsaved drafts
- `EventStreamProvider`
- `ActivityBar`
- page content
- right-hand `AgentDock`
- bottom `StatusBar`

Current pages:

- `projects`
- `agents`
- `tasks`
- `preview`
- `usage`
- `logs`
- `settings`

There is no standalone Terminals page in the current navigation. Terminals live
inside Agent Dock provider tabs and terminal drawers.

## API Layer

`frontend/src/api.ts` contains typed wrappers around backend endpoints. It is the
only normal HTTP API client used by UI components.

The two live paths are:

- `EventStreamProvider` in `stream.tsx` for SSE/polling events
- `TerminalPane` for provider PTY WebSockets

## Context Intelligence

The Settings page includes `frontend/src/components/ContextIntelligencePanel.tsx`.
It calls `api.contextPreview(task, maxTokens?)` for `POST /api/context/preview`
and exposes `api.contextReport(id)` for `GET /api/context/reports/{id}`.

## Event Store

`stream.tsx` is the only workspace event owner.

It:

- opens `/api/events/stream`
- falls back to `/api/events?cursor=`
- dedupes by event id
- resumes by cursor
- accumulates per-run stdout/stderr
- exposes hooks such as `useRunStream`, `useRecentEvents`, and
  `useStructuralRevision`

`SmoothStreamingText` is display-only. It smooths text already accumulated by
the stream store and never opens its own network connection.

## Agent Dock

Agent Dock components live in `frontend/src/components/dock/`.

| Component | Purpose |
| --- | --- |
| `AgentDock.tsx` | frame, resize, collapsed rail, tab/channel state, palette, composition |
| `AgentDockTabs.tsx` | controller/provider tab strip and toolbar buttons |
| `AgentDockTranscript.tsx` | controller messages, activity cards, approvals, live run blocks |
| `AgentDockLiveRun.tsx` | live output for a run from `useRunStream` |
| `AgentDockTerminalDrawer.tsx` | controller provider PTY drawer |
| `AgentDockComposer.tsx` | typed input composer and context chips |
| `AgentDockFooter.tsx` | workspace, git, provider, queue, run, health footer |

Controller tab behavior:

- completed messages render statically
- active controller output renders from live event deltas
- structural events render as compact `TimelineCard`s
- approvals render inline
- terminal drawer can open for the selected controller provider

Provider tab behavior:

- tabs for `codex`, `claude`, and `antigravity` are real PTY terminals through
  `TerminalPane`

## Terminal Pane

`frontend/src/components/TerminalPane.tsx` wraps xterm.js.

It:

- fetches `/api/terminals/{provider}/diagnostics`
- opens `WS /api/terminals/{provider}/ws`
- writes binary frames to xterm
- parses JSON metadata frames for lifecycle state
- shows resolving, missing, launching, ready, closed, and disconnected states
- supports restart

The same component is used by provider tabs and the Agent Dock terminal drawer.

## Tasks Page

`frontend/src/pages/TasksPage.tsx` is the task workbench.

Key pieces:

- `TaskDispatchMap`: provider-lane overview for controller, Codex, Claude,
  Antigravity, and local tools
- `StateCard`: current task/queue/approval summary
- `QueueStrip`: active/blocked/failed queue controls
- `StepChat`: prompt/output exchanges and live step output
- `ContinueReplyStream`: task-scoped controller continuation output
- `RawDetail`: paginated prompt/output/log/event/detail views

Active run text comes from `useRunStream(runId)` through the shared event store.
Finished task history is rebuilt from durable task files, runs, exchanges, and
events.

## Shared Presentation

Important reusable components:

- `InputComposer`
- `ConversationView` and `Message`
- `TimelineCard`
- `LiveActivityFeed`
- `TaskViews`
- `RawDetail`
- `StatusBadge`
- `CommandPalette`
- `ErrorBoundary`

`displayModel.ts` maps structured events to shared card models so Agent Dock and
Tasks render the same events at different densities.

## Frontend Checks

Targeted tests:

```bash
npm --prefix frontend run test -- src/lib/liveActivity.test.ts
npm --prefix frontend run test -- src/pages/tasks/TaskDispatchMap.test.tsx
npm --prefix frontend run test -- src/components/conversation/ConversationView.test.tsx
```

All frontend tests:

```bash
make test-frontend
```

Build:

```bash
make build
```
