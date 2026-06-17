# Streaming Renderer Decision

Command Line Interface Traffic Controller (CLIT Controller IDE) should render
generated text with a smooth CLI-like type-out, but the renderer should sit on
top of CLITC's shared event stream. It should not replace the workspace event
bus, open duplicate SSE connections, or own chat/task state.

## Decision

Use a small internal `SmoothStreamingText` renderer instead of installing
`react-text-stream`, `@magicul/react-chat-stream`, or a generic typewriter
package.

The backend remains authoritative for real streaming:

- `GET /api/events/stream` using SSE.
- `GET /api/events?cursor=<id>` as polling fallback.
- Redacted `textDelta` events emitted as provider/process text is generated or
  received.
- A single frontend workspace stream store that dedupes events, resumes from a
  cursor, and accumulates per-run text.

The renderer's job is only presentation: smooth newly received text deltas so
generated output feels like a real CLI stream.

## Package Comparison

### `react-text-stream`

Source: <https://github.com/amerani/react-text-stream>

Strengths:

- Purpose-built for Server-Sent Events.
- Provides a component and hook.
- Uses `EventSource`.
- TypeScript support.

Mismatch for CLITC:

- Latest package metadata declares React 19 peer dependencies, while CLITC uses
  React 18.
- It wants to open and own an SSE connection per component/hook.
- CLITC already has one workspace-scoped SSE connection with cursor resume,
  dedupe, polling fallback, and run/task routing.
- Using it directly would duplicate stream ownership and make dock/task/log
  synchronization harder.

Verdict: good for a simple isolated SSE text endpoint, not the right runtime
dependency for CLITC's shared event bus.

### `@magicul/react-chat-stream`

Source: <https://github.com/XD2Sketch/react-chat-stream>

Strengths:

- React 17+ peer dependency fits React 18.
- Designed for ChatGPT-like chat streams from a custom backend.
- Can display streamed responses as they arrive.

Mismatch for CLITC:

- The hook owns chat input, submit, loading state, and messages.
- CLITC already owns provider tabs, controller/direct channels, tasks, queue,
  approvals, retries, and durable replay.
- The package is chat-specific, while CLITC must smooth chat, task run output,
  logs, terminal-linked run output, approvals, and status transitions.
- It includes optional fake character pacing, but CLITC should render real
  backend deltas and only smooth presentation between received chunks.

Verdict: better React compatibility than `react-text-stream`, but too
stateful/chat-specific for CLITC.

### Generic Typewriter Packages

Examples: `react-simple-typewriter`, `typewriter-effect`.

Mismatch for CLITC:

- These are animation libraries, not streaming integrations.
- They usually start from a complete string.
- They risk faking streaming after the backend already has the full output.
- They do not understand event IDs, cursor resume, redaction, run IDs, task IDs,
  stderr/stdout channels, or queue/approval state.

Verdict: do not use for generated output.

## Internal Renderer Contract

Add `frontend/src/components/SmoothStreamingText.tsx`.

Props:

```ts
type SmoothStreamingTextProps = {
  text: string;
  active?: boolean;
  mode?: "prose" | "mono";
  maxChars?: number;
  className?: string;
};
```

Behavior:

- Accepts the already-redacted accumulated text from `useRunStream(...)`,
  `LiveOutput`, or a task/chat surface.
- Maintains an internal displayed string.
- When `text` grows, reveals the new suffix over animation frames.
- Uses `requestAnimationFrame`, not timers that drift under load.
- Reveals whole incoming text immediately when `active === false`.
- Reveals whole incoming text immediately when `prefers-reduced-motion: reduce`
  is active.
- Caps displayed text with `maxChars` for live log panes; full raw output remains
  in log files or expanders.
- Catches up quickly for large bursts so the UI does not lag far behind a fast
  CLI.
- Preserves whitespace and newlines.
- Does not mutate stream state, event state, task state, or chat state.

Recommended pacing:

- Small deltas: reveal at a readable CLI-like pace.
- Large bursts: reveal larger chunks per frame and cap total catch-up delay.
- Hard maximum lag: no more than roughly 500-800ms behind the latest received
  text for active runs.

## Integration Points

Use `SmoothStreamingText` in:

- `frontend/src/components/TaskViews.tsx`
  - `LiveOutput`
  - live run output cards
- `frontend/src/components/ChatPanel.tsx`
  - pending provider/controller reply output
  - active agent activity output
- `frontend/src/pages/TasksPage.tsx`
  - selected active task stream
  - live step output
- `frontend/src/pages/LogsPage.tsx`
  - only for live text rows where smoothing helps; keep historical logs static

Do not use smoothing for:

- Finished markdown replies.
- Historical task replay.
- Static log entries.
- Diff text.
- Commands, file paths, task IDs, provider IDs, or status labels.
- Any output that is being selected/copied, expanded, or inspected as raw text.

## Event Store Boundary

`SmoothStreamingText` must consume output after the event store has already:

- Received the SSE or polling event.
- Deduped by event ID.
- Resumed from cursor.
- Applied redaction from the backend.
- Accumulated `textDelta` into the correct run/chat stream.

It must not:

- Call `EventSource`.
- Call `/api/events/stream`.
- Call `/api/chat/send`.
- Own message arrays.
- Own provider/channel state.
- Own task replay state.
- Re-redact secrets in the browser as a primary safety boundary.

## Accessibility And Performance

- Respect `prefers-reduced-motion`.
- Avoid layout shift: live output containers need stable max height and scroll
  behavior.
- Keep auto-tail behavior only while the user is at or near the bottom.
- Do not steal scroll position when the user scrolls back to inspect earlier
  output.
- Use `aria-live="polite"` only on compact status text, not on large rapidly
  changing logs.
- Avoid re-rendering markdown on every character. For active mono output, render
  plain text. Convert to markdown only after completion if the surface calls for
  it.

## Implementation Checklist

- Add `SmoothStreamingText`.
- Replace live `<pre>{text}</pre>` blocks with `SmoothStreamingText` where output
  is still active.
- Keep finished output static.
- Keep `LiveOutput` responsible for framing, auto-tail, and sizing.
- Keep `streamStore` as the only SSE/polling owner.
- Add a focused unit or component test for:
  - progressive reveal on appended text
  - instant reveal when inactive
  - instant reveal when reduced motion is enabled
  - large burst catch-up
- Run `npm run build`.

## Acceptance Criteria

- Active provider chat appears progressively as text is generated or received.
- Active queued run output appears progressively as stdout/stderr chunks arrive.
- The right-hand Agent Dock and selected Tasks tab show the same accumulated
  stream from `streamStore`.
- The smoothing renderer never opens its own network stream.
- The app still has one workspace-scoped event subscription.
- Completed output does not animate again when revisited.
- Reduced-motion users see immediate text without animation.
- No `react-text-stream`, `@magicul/react-chat-stream`, generic typewriter
  package, or hosted chat SDK is added as a runtime dependency.
