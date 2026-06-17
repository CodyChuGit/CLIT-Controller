# Controller Backend Strategy

This docs set defines the path from the current beta backend to a fully functional
controller backend for Command Line Interface Terminal Controller (CLIT Controller IDE).

The current codebase already has the important primitives:

- FastAPI routes for projects, agents, chat, tasks, queue, usage, logs, and preview.
- File-backed workspaces under `<workspace>/.agentflow/`.
- Markdown task handoff files from `00_USER_GOAL.md` through `07_CODEX_FINAL_REVIEW.md`.
- A background queue dispatcher that runs one item per provider at a time.
- CLI subprocess execution, cancellation, redacted logs, provider probes, and usage tracking.
- A native React chat dock and PTY-backed Terminals page that can evolve into a
  VS Code-style Agent Dock without replacing backend traffic control.
- Directive-based traffic control through `agentflow-task`, `agentflow-queue`,
  `agentflow-run`, `agentflow-done`, and `agentflow-needs-user` blocks.

The missing backend work is not a new product concept. It is hardening the beta into
a durable traffic-control system with explicit state, resumable execution, stronger
provider contracts, predictable approvals, and a complete verification matrix.

## Documents

- [01 Target Capability](./01-target-capability.md) defines what "full functionality"
  means for the controller backend.
- [02 Architecture Contracts](./02-architecture-contracts.md) defines the backend
  components, state model, provider abstraction, and API/event contracts.
- [03 Implementation Roadmap](./03-implementation-roadmap.md) breaks the work into
  practical phases with acceptance criteria.
- [04 Verification And Operations](./04-verification-and-operations.md) defines the
  tests, recovery checks, safety checks, and production-readiness gates.
- [VS Code-Style Agent Dock And Tasks Tab](../vscode-style-agent-dock.md) defines
  the native feature-parity direction for Codex, Claude Code, Antigravity, and
  controller workflows.

## Guiding Decisions

- Keep CLITC local-first. The backend shells out to user-owned CLIs and stores
  project state under `.agentflow/`; it should not introduce hosted services or API
  key custody.
- Keep markdown handoff files as first-class artifacts. They are the audit trail that
  users and agents can inspect directly.
- Add stricter machine state beside the markdown. The current JSON files are useful,
  but full traffic control needs a durable run ledger, explicit state transitions, and
  restart recovery.
- Treat the controller as a policy-bound decision maker, not an unrestricted shell.
  The backend owns validation, approvals, workspace confinement, queue rules, and
  recovery behavior.
- Make automatic execution explainable. Every queued step, skipped step, direct
  command, provider failure, approval hold, retry, and final verdict needs a durable
  event.
- Build the right-hand Agent Dock and Tasks tab as CLITC-native VS Code-style
  parity surfaces. They should use backend task, queue, terminal, approval, and
  log contracts directly; they should not run VS Code plugins, load `.vsix`
  packages, or launch real VS Code.
- Treat live output as a shared backend contract for the Agent Dock and Tasks tab.
  Active runs should emit structured output, command lifecycle, approval, queue,
  error, and completion events that both surfaces can render immediately, with
  polling endpoints kept only as compatibility fallbacks.

## Current Backend Map

| Area | Current implementation | Strategic role |
|---|---|---|
| App shell | `backend/agentflow/app.py` | FastAPI app, route registration, dispatcher lifecycle |
| Task lifecycle | `backend/agentflow/task_service.py` | Task folders, step prompts, run completion hooks |
| Queue | `backend/agentflow/queue_service.py` | Persistent queue JSON and automatic dispatch |
| Controller chat | `backend/agentflow/chat_service.py` | CLI-backed chat and directive parsing |
| Execution | `backend/agentflow/process_runner.py` | Subprocess start, capture, cancellation, redacted logs |
| Providers | `backend/agentflow/provider_probe.py` | CLI detection, install/login helpers, model options |
| Routing | `backend/agentflow/routing_service.py` | Budget-aware recommendations and routing decisions |
| Usage | `backend/agentflow/usage_service.py` | Approximate usage, live best-effort provider usage |
| Workspace | `backend/agentflow/config.py`, `paths.py`, `workspace.py` | Local config and `.agentflow/` layout |
| Frontend contract | `frontend/src/api.ts`, `frontend/src/types.ts` | Existing API shapes the backend must preserve or version |
| Dock and task primitives | `frontend/src/components/ChatPanel.tsx`, `frontend/src/pages/TasksPage.tsx`, `frontend/src/pages/TerminalsPage.tsx` | Current chat, task, and terminal surfaces that form the basis for the future native Agent Dock and Tasks tab |
