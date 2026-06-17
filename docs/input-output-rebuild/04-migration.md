# 04 — Migration & Compatibility

## What changed in this stage (backend keystone + contracts)

1. **Controller protocol replaced.** `CLITC_RESULT_V1` ([controller_protocol.py](../../backend/agentflow/controller_protocol.py))
   is now the primary controller-action protocol; the regex `agentflow-*` directives
   are demoted to a fallback.
2. **Primacy wiring.** Every `parse_*` in [chat_directives.py](../../backend/agentflow/chat_directives.py)
   reads the protocol first; `chat_service` consumes them unchanged, so behavior is
   preserved while the deterministic path is authoritative.
3. **Prompts.** Both orchestrator prompts ([prompt_templates.py](../../backend/agentflow/prompt_templates.py))
   now teach only the v1 contract, generated from the action schema; legacy
   generation instructions were removed from normal operation.
4. **Typed contracts added.** Input + operational-event contracts
   ([io_contracts.py](../../backend/agentflow/io_contracts.py),
   [ioContracts.ts](../../frontend/src/lib/ioContracts.ts)).

## Compatibility policy (legacy directives)

Legacy `agentflow` JSON / `agentflow-*` markdown remain **only** as a bounded
migration adapter, with strict rules enforced by the parsers:

1. Parse the new protocol first.
2. A **valid** v1 block is authoritative.
3. A **present-but-invalid** v1 block yields no action and is **never** silently
   treated as legacy (no downgrade); `controller_failure()` surfaces the typed error.
4. Only when **no** v1 block exists are the legacy forms parsed (and marked).
5. Legacy generation prompts are already removed from normal operation.

**Removal condition:** once telemetry shows controllers emit `CLITC_RESULT_V1`
reliably (no `meta.source == "none"` controller turns over a sustained window), the
legacy parsers and the `agentflow` test fixtures can be deleted. Until then they are
retained, tested, and documented here.

## Sequenced next stage (frontend UI rebuild)

Not done in this stage; built on the contracts above and the existing shared
primitives ([03-component-system.md](03-component-system.md)). Concrete plan:

1. **InputComposer family** — one composer producing a typed `InputSubmission`
   (destination picker controller/provider/task, reference picker, draft lifecycle
   via `persist`, intent-aware task input). Fixes the discovery bug where the Tasks
   "Continue" box sends an unscoped controller message ignoring its `taskId`
   ([00-current-state.md](00-current-state.md)). Requires a backend route accepting
   `InputSubmission` (alongside the current `chatSend/chatDirect`).
2. **Typed event pipeline** — `event_bus` emits the `OutputEventEnvelope`; the
   stream store validates via `validateOutputEvent` and derives presentation records;
   page-local polling for event-covered state is removed.
3. **ChatPanel decomposition** — extract polling/queue/approval/command rendering
   into shared hooks/components; ChatPanel composes them.
4. **Presentation-record components** — CommandRecord/ToolRecord/SummaryRecord/
   FailureRecord at compact + detailed density, shared by Agent Dock, Tasks, Logs,
   and replay.

Each step is independently shippable and verifiable against the running app.

## Preserved invariants

CLI-first execution, official provider logins, local-first, workspace confinement,
provider routing, task/queue behavior, policy classification, approval gates, run
cancellation, single-flight, secret redaction, restart recovery, git safety,
localhost-only, SSE-primary + polling-fallback — all unchanged.
