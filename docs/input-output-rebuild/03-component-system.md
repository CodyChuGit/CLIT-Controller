# 03 — Component System

The frontend presentation system that the planes feed. Shared primitives are the
single source of rendering; surface-specific composition is allowed, but no surface
owns a competing renderer or event interpretation.

## Implemented shared primitives (the foundation)

| Primitive | File | Role |
|-----------|------|------|
| `ConversationView` | [conversation/ConversationView.tsx](../../frontend/src/components/conversation/ConversationView.tsx) | Canonical transcript: maps messages → `Message`, composes `useAutoScroll`, exposes a live `trailing` slot + empty state + "new output" affordance. |
| `Message` / `SystemNotice` / `ProviderMark` | [conversation/Message.tsx](../../frontend/src/components/conversation/Message.tsx) | The single chat-message renderer (user/assistant/controller/system). Used by ChatPanel; no surface re-implements it. |
| `Markdown` | [Markdown.tsx](../../frontend/src/components/Markdown.tsx) | The only Markdown renderer; builds React elements (no `dangerouslySetInnerHTML` for agent text) → XSS-safe. |
| `RawDetail` | [RawDetail.tsx](../../frontend/src/components/RawDetail.tsx) | Shared paginated raw viewer; ANSI-normalized for `stdout/stderr/log`. |
| `SmoothStreamingText` | [SmoothStreamingText.tsx](../../frontend/src/components/SmoothStreamingText.tsx) | Visual-only reveal of already-received text; static on completion/replay; reduced-motion aware. |
| `useAutoScroll` | [hooks/useAutoScroll.ts](../../frontend/src/hooks/useAutoScroll.ts) | Shared follow-near-bottom scroll with a pure, tested core. |
| `stripAnsi` | [lib/ansi.ts](../../frontend/src/lib/ansi.ts) | ANSI normalization for prose log views (xterm panes keep ANSI). |
| `coerceStreamEvent` | [lib/streamEvent.ts](../../frontend/src/lib/streamEvent.ts) | Network-boundary validation for live frames. |
| typed I/O contracts | [lib/ioContracts.ts](../../frontend/src/lib/ioContracts.ts) | `InputSubmission` + `OutputEvent` types + fail-safe validators. |

## Presentation-record model (target)

Components are selected by deterministic semantic type, not by sniffing prose:

```text
conversation message → Message
command              → CommandRecord  (label · live output · exit/duration · raw detail)
tool                 → ToolRecord
approval             → ApprovalCard   (shared)
failure              → FailureRecord  (title · impact · next action · raw detail)
summary              → SummaryRecord  (test/build/QA/completion, from contracts.py)
code / diff / log    → CodeBlock / DiffBlock / LogBlock (shared)
```

The card taxonomy and event→record projection live in
[displayModel.ts](../../frontend/src/lib/displayModel.ts).

## Sequenced (next stage)

The **InputComposer family** (one composer for controller / provider / task,
carrying a typed `InputSubmission`: destination picker, reference picker, draft
lifecycle, intent-aware task input) and the **explicit presentation-record
components** (CommandRecord/ToolRecord/SummaryRecord at compact + detailed density)
are the next stage, built on the primitives above. See
[04-migration.md](04-migration.md).

## External-library policy

Hand-written guards (consistent with `streamEvent.ts`) are used for runtime
validation to avoid a new dependency; a narrowly-scoped runtime-schema library
(e.g. zod) remains an option if the validator surface grows, wrapped behind
CLITC-owned modules. No hosted chat SDK, agent framework, external SSE/state owner,
or generic typewriter package is added.
