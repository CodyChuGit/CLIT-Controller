# 01 — Rebuilt I/O Architecture

The input/output boundary is rebuilt around **three separate planes**, correlated
by IDs but never collapsed into one arbitrary Markdown blob.

```text
PLANE 1 — Live Narrative        human-readable assistant/controller text, streamed
PLANE 2 — Operational Events    typed app-owned events (runs, commands, tasks,
                                 queue, approvals, failures, cancellation, summaries)
PLANE 3 — Deterministic Results validated, versioned records for controller actions
                                 and summaries
```

The UI must never infer authoritative behavior from narrative text; the backend
must never require the UI to parse prose to know what action occurred, what command
ran, whether approval is required, whether a task passed, or what the controller
decided.

## Module map

| Concern | Module | Status |
|---------|--------|--------|
| Deterministic controller result (Plane 3) | [controller_protocol.py](../../backend/agentflow/controller_protocol.py) | **Implemented** |
| Controller result is primary; legacy fallback | [chat_directives.py](../../backend/agentflow/chat_directives.py) | **Implemented** |
| Prompt contract generated from action schema | [prompt_templates.py](../../backend/agentflow/prompt_templates.py) | **Implemented** |
| Input submission + operational-event contracts (Plane 1/2) | [io_contracts.py](../../backend/agentflow/io_contracts.py), [ioContracts.ts](../../frontend/src/lib/ioContracts.ts) | **Implemented (contracts)** |
| Summaries (Plane 3) | [contracts.py](../../backend/agentflow/contracts.py) | Implemented (prior) |
| Live transport (SSE + polling) | [event_bus.py](../../backend/agentflow/event_bus.py), [routes_state.py](../../backend/agentflow/api/routes_state.py), [stream.tsx](../../frontend/src/stream.tsx) | Preserved; typed-event migration sequenced |
| Network-boundary event validation | [streamEvent.ts](../../frontend/src/lib/streamEvent.ts) | Implemented (prior) |
| Shared message renderer / transcript | [conversation/Message.tsx](../../frontend/src/components/conversation/Message.tsx), [ConversationView.tsx](../../frontend/src/components/conversation/ConversationView.tsx) | Implemented (prior) |
| One Markdown renderer (XSS-safe) | [Markdown.tsx](../../frontend/src/components/Markdown.tsx) | Implemented (prior) |
| ANSI normalization for prose logs | [ansi.ts](../../frontend/src/lib/ansi.ts) | Implemented (prior) |
| Shared auto-scroll | [useAutoScroll.ts](../../frontend/src/hooks/useAutoScroll.ts) | Implemented (prior) |
| Streaming text (visual smoothing only) | [SmoothStreamingText.tsx](../../frontend/src/components/SmoothStreamingText.tsx) | Preserved |

## Control flow (controller turn)

```text
typed InputSubmission (destination + intent explicit)
  → backend chat_service builds a typed prompt (result_contract_prompt synced to schema)
  → controller CLI streams NARRATIVE deltas  → event_bus → SSE → UI (live, before completion)
  → controller emits one CLITC_RESULT_V1 block
  → controller_protocol validates it (Plane 3)
     • valid   → action translated to existing execution (create_task/queue_steps/
                 run_command/complete_task/request_user); operational events emitted
     • invalid → typed FailureRecord; NO state mutation; failure card; narrative kept
  → summaries (Plane 3) emitted as validated records, referenced by event range
```

## What is implemented now vs sequenced

**Implemented + tested this stage** (the architectural keystone):
- The deterministic controller protocol and its primacy over the regex directives,
  with legacy demoted to a marked, no-silent-downgrade fallback and removed from
  prompt generation.
- The typed input + operational-event + result contracts (backend + frontend
  mirror), runtime-validated and version-safe.

**Sequenced (next stage, see [04-migration.md](04-migration.md))** — the frontend
UI rebuild on top of these contracts: the InputComposer family (typed destination
picker, drafts, intent-aware task input replacing the unscoped "Continue" box), the
stream store emitting/consuming the typed `OutputEvent` envelope end-to-end, the
ChatPanel decomposition, and the presentation-record taxonomy. The shared
primitives above (ConversationView/Message, one Markdown renderer, ANSI, auto-scroll,
streamEvent validation) are already the foundation for that stage.
