# API Reference

Base URL in development: `http://localhost:8787/api`.

All normal HTTP endpoints return JSON. Live managed output uses Server-Sent
Events. Interactive provider terminals use WebSockets.

Workspace-scoped routes require a current workspace unless noted.

## Health

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Backend health and version. |

## Projects

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/projects/current` | Current workspace and routing. |
| POST | `/api/projects/workspace` | Set current workspace. |
| GET | `/api/projects/tree` | Workspace file tree. |
| GET | `/api/projects/file?path=` | Read text file. |
| POST | `/api/projects/file` | Save text file. |
| GET | `/api/projects/git` | Compact git info. |
| GET | `/api/projects/git/status` | Full git status. |
| GET | `/api/projects/git/file-diff?path=&staged=` | File diff. |
| POST | `/api/projects/git/stage` | Stage file or all. |
| POST | `/api/projects/git/unstage` | Unstage file. |
| POST | `/api/projects/git/commit` | Commit staged changes. |
| POST | `/api/projects/open-folder` | Open workspace folder on macOS. |
| GET | `/api/projects/settings` | Routing/templates/models/Headroom/Ponytail/settings paths. |
| POST | `/api/projects/settings` | Update settings. |

## Agents

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/agents` | List provider definitions and cached status. |
| POST | `/api/agents/check` | Probe one provider. |
| POST | `/api/agents/check-all` | Probe all providers. |
| POST | `/api/agents/install` | Start provider install command. |
| POST | `/api/agents/login` | Launch or return provider login command. |
| POST | `/api/agents/model` | Set or clear provider model. |

## Chat And Input

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/chat` | Chat state, provider channels, pending run ids. |
| POST | `/api/chat/send` | Controller chat. |
| POST | `/api/chat/direct` | Direct provider chat. |
| POST | `/api/chat/submit` | Typed input route for controller, provider, or task destination. |
| POST | `/api/chat/stop` | Stop pending controller/provider response. |
| POST | `/api/chat/clear` | Clear a chat channel. |

`/api/chat/submit` accepts an `InputSubmission` with explicit destination:

- `{kind: "controller"}`
- `{kind: "provider", provider: "claude"}`
- `{kind: "task", taskId: "...", intent: "continue"}`

## Tasks

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/tasks` | List tasks. |
| POST | `/api/tasks` | Create task. |
| GET | `/api/tasks/{task_id}` | Task detail. |
| POST | `/api/tasks/{task_id}/run/{step}` | Run one step. |
| POST | `/api/tasks/{task_id}/run-full` | Run default full sequence. |
| POST | `/api/tasks/stop` | Stop one run or all active runs. |
| GET | `/api/tasks/{task_id}/exchanges` | Prompt/output exchanges by step. |
| GET | `/api/tasks/{task_id}/logs` | Task logs and in-memory runs. |
| GET | `/api/tasks/{task_id}/file?name=` | Read task artifact. |
| POST | `/api/tasks/{task_id}/open-folder` | Open task folder on macOS. |

## Queue

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/queue` | Queue state. |
| POST | `/api/queue/add` | Add steps to a task. |
| POST | `/api/queue/approve` | Approve a blocked queue item. |
| POST | `/api/queue/retry` | Retry item. |
| POST | `/api/queue/skip` | Skip item. |
| POST | `/api/queue/reroute` | Reroute item to provider. |
| POST | `/api/queue/remove` | Remove item. |
| POST | `/api/queue/clear` | Clear queue. |

## State, Events, Runs, Approvals

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/events?cursor=` | Polling fallback for live events. |
| GET | `/api/events/stream?cursor=` | SSE live event stream. |
| GET | `/api/runs/{run_id}` | Durable run record. |
| GET | `/api/approvals?pendingOnly=` | Approval list. |
| POST | `/api/approvals/{approval_id}/approve` | Approve command/action. |
| POST | `/api/approvals/{approval_id}/reject` | Reject command/action. |

SSE frames carry the full event as JSON in `data:` and use the event id as the
SSE `id`.

## Terminals

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/terminals/status` | Provider install status for terminal-capable agents. |
| GET | `/api/terminals/{provider}/diagnostics` | Resolved executable, workspace, lifecycle state, suggested action. |
| POST | `/api/terminals/{provider}/kill` | Kill/restart provider PTY session. |
| WS | `/api/terminals/{provider}/ws` | Bidirectional PTY terminal. |

Terminal WebSocket:

- server binary frames: raw PTY bytes
- server text frames: JSON metadata, e.g. `{"type":"meta","state":"ready"}`
- client text frames: `input`, `resize`, `kill`

## Usage

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/usage` | Usage counters and orchestration mode. |
| POST | `/api/usage/mode` | Set traffic-control mode. |
| POST | `/api/usage/provider-health` | Set manual provider health. |
| GET | `/api/usage/live?force=` | Best-effort live quota from supported CLIs. |
| GET | `/api/usage/recommendations` | Routing recommendation. |

## Logs

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/logs` | Redacted log entries and active managed runs. |
| POST | `/api/logs/clear-view` | Clear visible log view. |

## Preview

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/preview` | Preview state. |
| GET | `/api/preview/check` | TCP reachability check. |
| POST | `/api/preview/url` | Set preview URL. |
| POST | `/api/preview/start` | Start preview/dev server command. |
| POST | `/api/preview/stop` | Stop preview run. |
