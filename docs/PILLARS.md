# Product Pillars — the interaction model

CLIT Controller IDE is a local cockpit for orchestrating CLI coding agents. Its
defining experience — **Live Output Everywhere** — is not one SSE feature; it is a
coherent architecture built on five connected pillars. This document is the
authoritative statement of *what the product is trying to be from a user's goal*,
the acceptance criteria each pillar must meet, and where each is implemented.

The pillars are the success metrics: the test suites
([backend/tests/test_pillars.py](../backend/tests/test_pillars.py),
[test_headroom_service.py](../backend/tests/test_headroom_service.py),
[test_contracts.py](../backend/tests/test_contracts.py), and the frontend
`lib/*.test.ts`) exist to prove them. A change that improves one pillar while
materially weakening another needs explicit justification.

The combined architecture:

```text
minimal relevant canonical context
  → optional Headroom optimization (Pillar 1)
  → deterministic provider/controller contract (Pillar 5)
  → real provider or CLI generation
  → incremental canonical events (Pillar 2)
  → durable event persistence + redaction
  → workspace SSE
  → shared frontend event store
  → deterministic presentation records (Pillar 5)
  → consistent readable UI (Pillars 3 + 4)
  → structured completion summary (Pillar 5)
  → token-efficient agent hand-off (Pillar 1)
```

The canonical event stream is the source of operational truth; Headroom optimizes
model *input*; deterministic schemas define machine-consumed *meaning*; shared
components define human-readable *output*. No layer replaces another's job.

---

## Pillar 1 — Token saving and output speed

**User goal:** reach useful output faster while spending the fewest tokens that
still let the model/controller/tool act correctly. Not "minimize tokens" — "send
the smallest context that preserves everything required."

**How it is implemented**
- **Headroom integration** ([headroom_service.py](../backend/agentflow/headroom_service.py)):
  when enabled and a configured proxy is reachable, the `claude`/`codex` agents we
  spawn are routed through a Headroom context-optimization proxy
  (`ANTHROPIC_BASE_URL`/`OPENAI_BASE_URL`), which compresses prompt context. Start
  it with [scripts/headroom.sh](../scripts/headroom.sh) on `:8799`.
- **Existing token discipline** in the codebase: tailed+redacted run projections
  (`RunRecord.to_ledger`/`to_dict` tail before redacting), bounded buffers,
  cursor-resumable events (references to durable events instead of retransmitting),
  and compact directive/summary forms.

**Acceptance criteria** (✅ = covered, ◐ = partial, ☐ = recommended next)
- ✅ Headroom is **optional** (off by default) and **bounded** (300 ms cached
  reachability probe) — `test_headroom_service.py`.
- ✅ **Fail-open**: disabled or unreachable proxy → agents run direct; Headroom is
  never required for ordinary execution and never delays a spawn.
- ✅ Token-efficiency is reported as a versioned `TokenEfficiencyReport`
  ([contracts.py](../backend/agentflow/contracts.py)); unmeasured savings are
  `null`, never fabricated. Verify realized savings with
  `headroom agent-savings --check-perf`.
- ◐ Separate latency/token metrics (context-prep latency, time-to-first-token,
  original vs optimized tokens) are defined as a contract but not yet surfaced as a
  dashboard. See [LIMITATIONS.md](LIMITATIONS.md).

**Automatic rejections:** token cuts that drop required user constraints; Headroom
becoming required; Headroom delaying live output.

---

## Pillar 2 — True live CLI and LLM output

**User goal:** understand what the system is doing *while* providers, controllers,
agents, and commands are still active.

**Defining invariant:** the first usable chunk becomes persistable, transportable,
and renderable **before its producer completes**. Not: wait for the full response /
process exit / `communicate()`; not a typewriter animation over completed text;
not polling snapshots as the normal path.

**How it is implemented**
- [process_runner.py](../backend/agentflow/process_runner.py) reads child stdout/
  stderr incrementally (`_read_stream`, 4 KB chunks), decodes, redacts at a
  whitespace boundary (`_split_emittable`), and emits canonical deltas via
  [event_bus.py](../backend/agentflow/event_bus.py) as they arrive.
- [api/routes_state.py](../backend/agentflow/api/routes_state.py) serves these over
  SSE (`/api/events/stream`, cursor-resumable) with a polling fallback (`/api/events`).
- The frontend [stream.tsx](../frontend/src/stream.tsx) store applies validated
  frames; [SmoothStreamingText.tsx](../frontend/src/components/SmoothStreamingText.tsx)
  reveals genuine appends (snaps when inactive / reduced-motion).

**Acceptance criteria**
- ✅ A deterministic test proves a delta is visible while the run is still
  `running` (before exit) — `test_pillars.py::test_pillar2_output_is_visible_before_process_exits`.
- ✅ Distinct channels are preserved (assistant/controller/stdout/stderr/system/
  approval/failure) via `stream_kind` + channel, not one undifferentiated transcript.
- ✅ Queue/approval blockers stream immediately (every structural transition mirrors
  to the bus via `state_store.append_event`).

---

## Pillar 3 — Readable input and output presentation

**User goal:** read prose, commands, diffs, and results — not raw protocol, JSON
envelopes, or ANSI noise.

**How it is implemented**
- One markdown renderer ([Markdown.tsx](../frontend/src/components/Markdown.tsx))
  builds React elements (never `dangerouslySetInnerHTML` for agent text) → XSS-safe
  by construction (test in `Markdown.test.tsx`).
- ANSI normalization ([lib/ansi.ts](../frontend/src/lib/ansi.ts)) strips escape
  sequences from prose log/stdout/stderr views ([RawDetail.tsx](../frontend/src/components/RawDetail.tsx));
  live xterm terminals keep their ANSI.
- Progressive disclosure: `RawDetail` paginates raw output behind expanders;
  [displayModel.ts](../frontend/src/lib/displayModel.ts) maps events to a card
  taxonomy; [TimelineCard.tsx](../frontend/src/components/TimelineCard.tsx) renders
  compact/detailed densities.
- Secrets are redacted before transport ([redaction.py](../backend/agentflow/redaction.py),
  proven by `test_pillars.py::test_pillar3_secrets_never_reach_the_live_stream`).

**Acceptance criteria**
- ✅ Raw protocol/ANSI is not the primary UI; prose/code/commands/approvals/logs/
  failures are visually distinct; large output is collapsible; full detail retained.
- ◐ CLI normalization beyond ANSI (compiler/test/lint classification into a single
  Command surface) is partial — see [LIMITATIONS.md](LIMITATIONS.md).

---

## Pillar 4 — Consistent interfaces across every chat window

**User goal:** the Agent Dock, ChatPanel, provider chats, task replay, and approval
conversations feel like one product, not separate apps.

**How it is implemented**
- Shared primitives already own the rendering: `Markdown` (the only markdown
  renderer), `TimelineCard`, `RawDetail`, `Composer`, `SmoothStreamingText`,
  `TaskViews` (`LiveOutput`/`ApprovalCard`), and `displayModel.ts` (the single
  event→card projection).
- One event-interpretation pipeline: canonical event → `coerceStreamEvent`
  ([lib/streamEvent.ts](../frontend/src/lib/streamEvent.ts)) → `streamStore` →
  `displayModel` → shared component. Surfaces compose these; they do not each
  re-interpret event semantics.
- Shared auto-scroll: [hooks/useAutoScroll.ts](../frontend/src/hooks/useAutoScroll.ts)
  (follow-near-bottom, new-output affordance), with a pure tested core.

**Acceptance criteria**
- ✅ Exactly one markdown renderer (enforced by repo convention; no competing
  `parseSegments`).
- ✅ One validated event-interpretation pipeline.
- ✅ One shared chat-message renderer: `conversation/Message` + `ConversationView`
  (composing the shared `useAutoScroll`); ChatPanel and the conversation view use
  it, so no surface keeps a competing message renderer.
- ◐ `ConversationView` is adopted by the dock; the per-step task-replay layout
  still composes the shared prose/raw/streaming primitives directly (valid
  surface composition); reduced-motion is honored in streaming text but not audited
  on every surface. See [LIMITATIONS.md](LIMITATIONS.md).

---

## Pillar 5 — Deterministic text output formats

**User goal:** output that is reliably parsable, styled, summarized, replayed, and
compared — without guessing the meaning of arbitrary prose.

**Three layers (kept separate):**
1. **Canonical event envelope** — durable, backend-owned (state_store/event_bus):
   identity, workspace, type, ordering, channel, refs, redaction/truncation flags.
2. **Deterministic semantic content** — [contracts.py](../backend/agentflow/contracts.py):
   versioned, `kind`-discriminated Pydantic models for controller directives,
   command/test/task summaries, failures, approvals, hand-offs, token reports.
3. **Presentation model** — [displayModel.ts](../frontend/src/lib/displayModel.ts):
   frontend records that select shared components by `kind`.

**Acceptance criteria**
- ✅ Machine-consumed output uses validated schemas; controller directives are
  validated records (`chat_directives.controller_directive_records`), not prose
  guesses.
- ✅ Every contract is **versioned** (`version` + `kind`); invalid/unknown/old
  payloads fail safely via `contracts.validate` (structured `FailureRecord`, no
  crash, no correction loop) — `test_contracts.py`.
- ✅ Network input is validated at the boundary (`coerceStreamEvent`).
- ✅ Structured summaries reference full output by event range
  (`OutputRef`) instead of re-embedding it — canonical history is never discarded.
- ✅ Native structured controller output: the controller emits a deterministic,
  versioned, sentinel-framed result (`CLITC_RESULT_V1`, see
  [input-output-rebuild/02-protocols.md](input-output-rebuild/02-protocols.md))
  with a closed action union, validated before it can act; invalid output mutates no
  state. It is now the primary protocol (`controller_protocol.py`), with the legacy
  `agentflow` JSON / markdown directives demoted to a no-silent-downgrade fallback
  and removed from prompt generation.

---

## Status legend

✅ implemented & tested · ◐ partial (tracked in [LIMITATIONS.md](LIMITATIONS.md) /
[ROADMAP.md](ROADMAP.md)) · ☐ planned. See [FEATURE_STATUS.md](FEATURE_STATUS.md)
for the per-feature matrix.
