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

1. **InputComposer family — DONE.** `components/input/InputComposer.tsx` produces a
   typed `InputSubmission` (explicit destination + intent, draft lifecycle via
   `persist`: persists per (workspace, destination), restores on reload, clears only
   on confirmed submit, preserved on failed submit). Backed by `POST /api/chat/submit`
   ([routes_chat.py](../../backend/agentflow/api/routes_chat.py)) which validates the
   submission and dispatches by destination, threading `focus_task_id` for a task
   destination. **Fixes the Tasks-"Continue"-ignores-taskId bug end-to-end** (the
   taskId now reaches the backend, scoping the controller to that task) — verified in
   the browser (the POST body carries `destination.taskId`) and by integration tests.
   Adopted on the Tasks page **and in ChatPanel** (controller + provider channels):
   the dock derives the destination from the active channel
   (controller→`{kind:"controller"}` with the engine pick in `context.provider`;
   provider tab→`{kind:"provider",provider}`) and gets per-channel drafts for free.
   All three chat surfaces now share one composer + the typed `/api/chat/submit`
   contract — browser-verified for each. The controller's old `chatSend`/`chatDirect`
   branch and its `input`/`sending` state were removed.
2. **Typed event pipeline — DONE (additive).** `event_bus` attaches a typed,
   discriminated `payload` to each semantic event (legacy flat fields preserved so
   the live stream is untouched); `coerceStreamEvent` validates it (`validatePayload`,
   fail-safe) and `lib/presentation.recordFromEvent` derives `PresentationRecord`s
   from the payload type — not from `type` string maps/prose.
3. **ChatPanel decomposition — DONE (data layer).** Fetching/polling extracted to
   `hooks/useDockData.ts` (chat/queue/logs/approvals + visibility-aware timer +
   event-driven refetch + `busy`); ChatPanel dropped ~220 lines and now composes
   rendering. Message rendering already uses the shared `conversation/Message`.
   Remaining: TasksPage still has its own queue/approvals polling (a separate
   `useDockData`-style extraction).
4. **Presentation-record components — DONE.** `components/records/RecordView`
   (CommandRecord/FailureRecord/SummaryRecord) selected by record kind; narrative →
   `conversation/Message`, approval → the shared `ApprovalCard`. Wiring these into
   every surface's live render (replacing the bespoke AgentActivity/displayModel
   card paths) is the remaining incremental adoption.

Each step is independently shippable and verifiable against the running app.

## Preserved invariants

CLI-first execution, official provider logins, local-first, workspace confinement,
provider routing, task/queue behavior, policy classification, approval gates, run
cancellation, single-flight, secret redaction, restart recovery, git safety,
localhost-only, SSE-primary + polling-fallback — all unchanged.
