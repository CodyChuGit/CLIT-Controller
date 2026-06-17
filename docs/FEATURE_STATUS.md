# Feature Status

A traced, evidence-based inventory of every feature in CLIT Controller IDE /
AgentComposer. Each row was confirmed by reading the actual handler, not the name
of a route or a button. Status definitions:

- **Implemented** — wired end to end (UI → API → service → disk/process) and
  exercised in normal use.
- **Partially implemented** — works, but with a real gap (missing UI, narrow
  provider support, or limited scope) called out in Notes.
- **Mocked** — present in the codebase but returns canned/placeholder data, or is
  defined but has no live producer/consumer.
- **Experimental** — works but opt-in, unverified at scale, or best-effort by design.
- **Planned** — documented and/or scaffolded, no working code path.
- **Deprecated** — superseded; retained only for migration/compat.

Product context lives in [docs/PILLARS.md](PILLARS.md); system shape in
[docs/ARCHITECTURE.md](ARCHITECTURE.md); operations in
[docs/OPERATIONS.md](OPERATIONS.md); the trust model in
[docs/SECURITY.md](SECURITY.md). This document is the *what-works* map; those are
the *how/why*.

## Inventory

| Feature | Status | Frontend | Backend | Tests | Notes |
| --- | --- | --- | --- | --- | --- |
| Workspace selection | Implemented | [ProjectsPage.tsx](../frontend/src/pages/ProjectsPage.tsx), [api.ts](../frontend/src/api.ts) `setWorkspace` | [routes_projects.py](../backend/agentflow/api/routes_projects.py) `POST /api/projects/workspace`, [config.py](../backend/agentflow/config.py) | [test_recovery.py](../backend/tests/test_recovery.py) | Sets the single active workspace in `~/.agentflow/config.json`; runs startup recovery on select. |
| File tree | Implemented | [FileTree.tsx](../frontend/src/components/FileTree.tsx) | `GET /api/projects/tree` → [workspace.py](../backend/agentflow/workspace.py) `scan_tree` | [test_workspace_write.py](../backend/tests/test_workspace_write.py) | Bounded recursive scan of the workspace. |
| File read / editor | Implemented | [CodeReader.tsx](../frontend/src/components/CodeReader.tsx), `App.tsx` editor tabs + drafts | `GET/POST /api/projects/file` → `read_text_file`/`write_text_file` | [test_workspace_write.py](../backend/tests/test_workspace_write.py) | Read + save with path confinement; unsaved drafts persist across tab/page switches. |
| Git info / source-control panel | Implemented | [SourceControlPanel.tsx](../frontend/src/components/SourceControlPanel.tsx) (in ProjectsPage) | [git_service.py](../backend/agentflow/git_service.py): `git_info`, `status_files`, `file_diff`, `full_diff`, `stage`, `unstage`, `commit` | [test_git_service.py](../backend/tests/test_git_service.py) | Stage/unstage/commit/diff over the real `git` CLI. Push/pull/fetch are not in the panel — they route through the approval policy when a command asks for them. |
| Open folder in Finder | Partially implemented | `openWorkspaceFolder`, `openTaskFolder` | `POST /api/projects/open-folder`, `POST /api/tasks/{id}/open-folder` | — | macOS-only (`open`); returns HTTP 400 elsewhere. |
| Provider detection | Implemented | [AgentsPage.tsx](../frontend/src/pages/AgentsPage.tsx), [ProviderCard.tsx](../frontend/src/components/ProviderCard.tsx) | [provider_probe.py](../backend/agentflow/provider_probe.py): `list_providers`, `check_provider`, `check_all` | [test_provider_install.py](../backend/tests/test_provider_install.py) | Runs each CLI's real `--version`/status; caches to `~/.agentflow/providers.json`; resolves `~/.local/bin` etc. |
| Provider one-click install | Implemented | `installAgent` | `POST /api/agents/install` → `install_provider` | [test_provider_install.py](../backend/tests/test_provider_install.py) | Runs the provider's real install command in the background; refreshes the cache on completion. `omlx` has no installer (returns `no_installer`). |
| Provider login / setup | Partially implemented | `loginAgent` | `POST /api/agents/login` → `login_provider` | — | macOS opens a `.command` in Terminal; elsewhere it returns the command string to run manually. Login itself happens in that external terminal. |
| Provider model selection | Implemented | ProviderCard model picker | `POST /api/agents/model` → `config.update_settings(models=…)`; `antigravity` refreshes options from `agy models` | [test_model_flag.py](../backend/tests/test_model_flag.py) | Only the 3 agent providers (codex/claude/antigravity) are model-editable. |
| Orchestrator chat | Implemented | [ChatPanel.tsx](../frontend/src/components/ChatPanel.tsx) | [chat_service.py](../backend/agentflow/chat_service.py) `send`; `GET/POST /api/chat*` | [test_chat_service.py](../backend/tests/test_chat_service.py) | Persistent chat in `chat.json`, executed via the user's own CLI; replays clipped history into the prompt. |
| Direct agent chat | Implemented | ChatPanel per-provider channels | `chat_service.send_direct`; `POST /api/chat/direct` | [test_chat_service.py](../backend/tests/test_chat_service.py) | One channel per agent CLI; no directives or task creation. |
| Controller directives (task/queue/run/done/needs-user) | Implemented | rendered in chat + timeline | [chat_directives.py](../backend/agentflow/chat_directives.py) parsed in `chat_service.send` / `orchestrator_consult` | [test_task_directive.py](../backend/tests/test_task_directive.py) | Fenced ` ```agentflow-* ` blocks in agent output create tasks, queue steps, and run commands. Run directives capped at 3 per turn. |
| Task creation + handoff files | Implemented | TasksPage | [task_service.py](../backend/agentflow/task_service.py) `create_task`; `POST /api/tasks` | [test_task_service.py](../backend/tests/test_task_service.py) | Writes markdown handoff files + `task.json` per task under `.agentflow/tasks/`. |
| Task step execution | Implemented | TasksPage step controls | `task_service.run_step`; `POST /api/tasks/{id}/run/{step}` | [test_task_service.py](../backend/tests/test_task_service.py), [test_run_lifecycle.py](../backend/tests/test_run_lifecycle.py) | Runs one workflow step as a real subprocess; snapshots artifacts + changed code; validates step transitions. Steps defined in [workflow.py](../backend/agentflow/workflow.py). |
| Full sequence run | Implemented | TasksPage "run full" | `task_service.run_full_sequence` | [test_task_service.py](../backend/tests/test_task_service.py) | codex_spec → claude_implement → gemini_qa → codex_review; pauses before Claude when its health is RED; Budget Saver skips the spec for small goals. |
| Task flow chart | Implemented | [TaskFlowChart.tsx](../frontend/src/pages/tasks/TaskFlowChart.tsx) | step previews from `get_task_detail` (`stepPreviews`, `recommendation`) | — | Renders per-step provider/reads/writes/command preview from the backend's deterministic preview. |
| Step exchanges / logs viewer | Implemented | TasksPage, [StepChat.tsx](../frontend/src/pages/tasks/StepChat.tsx) | `step_exchanges`, `list_task_logs`, `read_task_file`; `GET /api/tasks/{id}/{exchanges,logs,file}` | [test_task_service.py](../backend/tests/test_task_service.py) | Prompt → output pairs rebuilt from on-disk logs (survive restart). |
| Execution queue + dispatcher | Implemented | TasksPage queue view | [queue_service.py](../backend/agentflow/queue_service.py): `dispatcher_loop`, `tick`, `dispatch_item`; `/api/queue/*` | [test_queue_service.py](../backend/tests/test_queue_service.py), [test_queue_ops.py](../backend/tests/test_queue_ops.py) | One step per provider at a time, intra-task order preserved, durable in `queue.json`; settles finished runs and blocks later steps of failed tasks. |
| Queue ops (retry/skip/reroute/remove/clear) | Implemented | queue item buttons | `retry_item`, `skip_item`, `reroute_item`, `remove_item`, `clear_queue` | [test_queue_ops.py](../backend/tests/test_queue_ops.py) | Reroute runs the step on a non-default provider via `providerOverride`. |
| Closed-loop controller consults | Implemented | reflected in chat + timeline | `queue_service._request_consult` → `chat_service.orchestrator_consult` | [test_queue_service.py](../backend/tests/test_queue_service.py) | After each step of an orchestrated task, the controller is re-consulted; capped at 6 consults/task. |
| Approvals (commands) | Implemented | ChatPanel approval prompts | [policy_service.py](../backend/agentflow/policy_service.py) `classify_action`; [state_store.py](../backend/agentflow/state_store.py) approvals; `/api/approvals/*` | [test_policy_service.py](../backend/tests/test_policy_service.py), [test_routes_state.py](../backend/tests/test_routes_state.py) | Three-way policy: allow / require_approval / deny. Risky commands create a durable approval; approving it runs the command. ADR: [adr/0001-auto-run-policy-allowlist.md](adr/0001-auto-run-policy-allowlist.md). |
| Live event streaming (SSE) | Implemented | [stream.tsx](../frontend/src/stream.tsx) `EventStreamProvider` | [event_bus.py](../backend/agentflow/event_bus.py); `GET /api/events/stream` | [test_streaming.py](../backend/tests/test_streaming.py) | Cursor-resumable SSE; honors `Last-Event-ID`; heartbeat keep-alive. |
| Live event polling fallback | Implemented | stream.tsx polling path | `GET /api/events?cursor=` | [test_streaming.py](../backend/tests/test_streaming.py) | Same in-memory bus as SSE; dedupe by `id`. Frames coerced via [streamEvent.ts](../frontend/src/lib/streamEvent.ts). |
| Live run/text deltas in UI | Implemented | [SmoothStreamingText.tsx](../frontend/src/components/SmoothStreamingText.tsx), [TimelineCard.tsx](../frontend/src/components/TimelineCard.tsx) | `process_runner` publishes `text_delta` to the bus | [test_streaming.py](../backend/tests/test_streaming.py) | Pillar 2/3; ANSI handled by [ansi.ts](../frontend/src/lib/ansi.ts); autoscroll by [useAutoScroll.ts](../frontend/src/hooks/useAutoScroll.ts). |
| PTY terminals over WebSocket | Implemented | [TerminalsPage.tsx](../frontend/src/pages/TerminalsPage.tsx) (xterm) | [terminal_service.py](../backend/agentflow/terminal_service.py); `WS /api/terminals/{provider}/ws` | [test_terminal_service.py](../backend/tests/test_terminal_service.py), [test_routes_terminals.py](../backend/tests/test_routes_terminals.py) | Per-(workspace,provider) sessions, scrollback snapshot on connect, origin-checked handshake, orphan sweep on startup. |
| Preview dev-server | Implemented | [PreviewPage.tsx](../frontend/src/pages/PreviewPage.tsx) (iframe) | [routes_preview.py](../backend/agentflow/api/routes_preview.py): start/stop/check/url | — | Runs the workspace dev command as a managed run; TCP reachability check; URL confined to localhost. No dedicated test module. |
| Usage / budget tracking | Implemented | [UsagePage.tsx](../frontend/src/pages/UsagePage.tsx), [UsageHealthBadge.tsx](../frontend/src/components/UsageHealthBadge.tsx) | [usage_service.py](../backend/agentflow/usage_service.py); `/api/usage*` | [test_usage_service.py](../backend/tests/test_usage_service.py) | Approximate per-provider counters + manual health (green/yellow/red) in `usage.json`; drives routing. |
| Traffic-control / budget modes | Implemented | [BudgetModePicker.tsx](../frontend/src/components/BudgetModePicker.tsx) | `set_orchestration_mode`; consumed in task/queue/policy flows | [test_usage_service.py](../backend/tests/test_usage_service.py), [test_routing_service.py](../backend/tests/test_routing_service.py) | maximum_quality / balanced / budget_saver / manual_approval; manual_approval gates every agent run. |
| Live quota from CLIs | Partially implemented | UsagePage live panel | `usage_service.live_usage`, `codex_live_usage`, `claude_live_usage`; `GET /api/usage/live` | [test_usage_service.py](../backend/tests/test_usage_service.py) | Real data only for Codex (parsed from `~/.codex` session files) and Claude (`claude -p "/usage"`). Antigravity exposes no usage call → manual limit only. Best-effort, cached ~120s. |
| Routing recommendations | Implemented | [RoutingRecommendationCard.tsx](../frontend/src/components/RoutingRecommendationCard.tsx) | [routing_service.py](../backend/agentflow/routing_service.py) `recommend`; `GET /api/usage/recommendations` | [test_routing_service.py](../backend/tests/test_routing_service.py) | Health- and mode-aware guidance + `ROUTING_DECISIONS.md` per task. Advisory text/flags, not an automatic provider switch. |
| Headroom token-saving proxy | Implemented (opt-in) | settings (`headroom` in `/api/projects/settings`) | [headroom_service.py](../backend/agentflow/headroom_service.py); injected in `process_runner` | [test_headroom_service.py](../backend/tests/test_headroom_service.py) | Pillar 1. Off by default; fail-open. Injects `ANTHROPIC_BASE_URL`/`OPENAI_BASE_URL` for claude/codex only when enabled and the proxy is reachable. Antigravity is excluded. |
| Deterministic contracts — directive forms | Partially implemented | not consumed | [contracts.py](../backend/agentflow/contracts.py) via `chat_directives.controller_directive_records` | [test_contracts.py](../backend/tests/test_contracts.py) | Pillar 5. The directive contracts validate, but the live chat path still uses the legacy `parse_*` parsers directly; `controller_directive_records` is exercised only by tests. |
| Deterministic contracts — result/summary schemas | Mocked | not consumed | `contracts.py`: CommandSummary, TestSummary, TaskSummary, AgentHandoff, ApprovalRequest, FailureRecord, TokenEfficiencyReport | [test_contracts.py](../backend/tests/test_contracts.py) | Defined and `validate()`-tested, but no live producer emits them and no frontend reader selects on their `kind`. Schema-only today. |
| Durable state ledgers + recovery | Implemented | (consumed indirectly) | `state_store.py`: events/runs/approvals; `recover_workspace` on startup + workspace select | [test_state_store.py](../backend/tests/test_state_store.py), [test_recovery.py](../backend/tests/test_recovery.py) | Atomic JSON ledgers; a restart never leaves a run/step/queue item stuck `running`. |
| Secret redaction | Implemented | (server-side only) | [redaction.py](../backend/agentflow/redaction.py); applied in event_bus + log/output paths | [test_redaction.py](../backend/tests/test_redaction.py), [test_redaction_payloads.py](../backend/tests/test_redaction_payloads.py) | Defense-in-depth: redaction happens before persist/broadcast; never in the browser. |
| CORS / CSRF / WS origin guard | Implemented | — | [origins.py](../backend/agentflow/origins.py), `OriginGuardMiddleware` in [app.py](../backend/agentflow/app.py) | [test_csrf.py](../backend/tests/test_csrf.py), [test_security_fixes.py](../backend/tests/test_security_fixes.py), [test_hardening.py](../backend/tests/test_hardening.py) | Shared allowlist across CORS, the CSRF middleware, and the WebSocket handshake. |
| Command palette | Implemented | [CommandPalette.tsx](../frontend/src/components/CommandPalette.tsx) | (client-only navigation) | — | Keyboard-driven page/action switcher. |
| PWA / app mode | Implemented | [manifest.webmanifest](../frontend/public/manifest.webmanifest), [sw.js](../frontend/public/sw.js), SW registered in `main.tsx` (PROD only) | served from `frontend/dist` by `app.py` | — | Standalone display + maskable icons; SW registers only in production builds. See [pwa-chrome-app-mode.md](pwa-chrome-app-mode.md). |
| Ollama provider | Partially implemented | shown on AgentsPage | detect/install/version only in `provider_probe.py` | [test_provider_install.py](../backend/tests/test_provider_install.py) | Detectable and installable, but **not** an `AGENT_PROVIDER_IDS` member — no routing/chat/task/terminal path uses it. Reserved for future local summarization/cheap routing. |
| omlx · Apple MLX provider | Partially implemented | shown on AgentsPage | detect/version only (`no_installer`) in `provider_probe.py` | — | Detectable across several MLX binary names; not orchestratable (not in `AGENT_PROVIDER_IDS`). Future on-device summarization/routing. |
| Local voice I/O | Planned | none | none | none | No code references (`grep` for voice/speech/STT/TTS finds nothing). Documented direction only — see [local-voice-io.md](local-voice-io.md) (MLX Parakeet STT + mlx-swift-dots-tts). |
| Gemini CLI provider | Deprecated | — | migration in `usage_service.ensure_usage` (carries `gemini` stats → `antigravity`) | [test_usage_service.py](../backend/tests/test_usage_service.py) | Superseded by the Antigravity CLI (`agy`). Only the usage-migration shim remains. |

## Production-ready (Implemented)

Wired end to end and used in normal operation:

- Workspace selection, file tree, file read/editor (with persisted drafts).
- Git info and the source-control panel (status, diff, stage/unstage, commit).
- Provider detection, one-click install, and model selection.
- Orchestrator chat, direct agent chat, and controller directive handling.
- Task creation + handoff files, single-step and full-sequence execution, the
  flow chart, and the step-exchange/log viewers.
- Execution queue + dispatcher, queue ops (retry/skip/reroute/remove/clear), and
  closed-loop controller consults.
- Command approvals backed by the three-way policy service.
- Live event streaming (SSE + polling fallback) and live run/text deltas in the UI.
- PTY terminals over WebSocket.
- Usage/budget tracking, traffic-control modes, and routing recommendations.
- Durable state ledgers with startup/select recovery, secret redaction, and the
  CORS/CSRF/WS origin guard.
- Command palette and PWA/app mode.

## Partial

Works with a stated gap:

- **Open folder in Finder** and **provider login/setup** — macOS-only behavior;
  off-macOS they return the command string for the user to run manually.
- **Live quota from CLIs** — real data only for Codex and Claude; Antigravity has
  no headless usage call, so it relies on manual limits. Best-effort and cached.
- **Routing recommendations** — advisory output and flags; it does not flip the
  active provider automatically.
- **Deterministic contracts (directive forms)** — validate correctly but are not
  yet on the live chat path (legacy parsers still drive execution).
- **Ollama** and **omlx** providers — detectable/installable on the Agents page,
  but not members of `AGENT_PROVIDER_IDS`, so no chat/task/queue/terminal path
  routes to them.

## Mocked

Present but not producing/consuming live data:

- **Deterministic contracts — result/summary schemas** (CommandSummary,
  TestSummary, TaskSummary, AgentHandoff, ApprovalRequest, FailureRecord,
  TokenEfficiencyReport). Defined and `validate()`-tested; no live emitter and no
  UI reader keys off their `kind` today.

## Experimental

Opt-in or best-effort by design:

- **Headroom token-saving proxy** — off by default, fail-open; only injected for
  claude/codex when enabled and the proxy is reachable (Pillar 1, opt-in).

## Planned

Documented, no working code path:

- **Local voice I/O** — STT/TTS direction described in
  [local-voice-io.md](local-voice-io.md); no implementation exists.

## Deprecated

- **Gemini CLI provider** — replaced by the Antigravity CLI; only the
  usage-stat migration shim remains.

## Cross-references

- Pillars and interaction model: [docs/PILLARS.md](PILLARS.md)
- Architecture: [docs/ARCHITECTURE.md](ARCHITECTURE.md)
- Operations: [docs/OPERATIONS.md](OPERATIONS.md)
- Security model: [docs/SECURITY.md](SECURITY.md)
- Engineering standards: [docs/ENGINEERING_STANDARDS.md](ENGINEERING_STANDARDS.md)
- Audit trail: [docs/audit/INITIAL_AUDIT.md](audit/INITIAL_AUDIT.md),
  [docs/audit/FINAL_REPORT.md](audit/FINAL_REPORT.md)
- Auto-run policy decision: [docs/adr/0001-auto-run-policy-allowlist.md](adr/0001-auto-run-policy-allowlist.md)
