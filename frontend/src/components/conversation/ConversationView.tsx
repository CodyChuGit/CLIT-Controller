import { type ReactNode } from "react";

import type { ChatMessage } from "../../types";
import { useAutoScroll } from "../../hooks/useAutoScroll";
import { Message } from "./Message";

/* Pillar 4 — the canonical scrollable transcript for any chat-like surface.
   Renders a list of messages with the single shared Message renderer and the
   shared auto-scroll behaviour (follow near bottom; "new output" affordance when
   scrolled up). A surface may pass `trailing` to append live in-flight content
   (e.g. a streaming reply) below the committed messages, and `empty` for the
   empty state. Surface-specific chrome composes this; it does not re-interpret
   message presentation. */
export function ConversationView({
  messages,
  direct = false,
  trailing,
  empty,
  className = "",
}: {
  messages: ChatMessage[];
  direct?: boolean;
  trailing?: ReactNode;
  empty?: ReactNode;
  className?: string;
}) {
  // Re-evaluate scroll position on new messages or new live content.
  const { ref, atBottom, onScroll, scrollToBottom } = useAutoScroll<HTMLDivElement>(
    `${messages.length}:${typeof trailing === "string" ? trailing.length : trailing ? 1 : 0}`,
  );

  return (
    <div className="relative min-h-0 flex-1">
      <div
        ref={ref}
        onScroll={onScroll}
        className={`min-h-0 flex-1 space-y-2.5 overflow-y-auto px-3 py-3 ${className}`}
      >
        {messages.length === 0 && !trailing ? empty : null}
        {messages.map((m, i) => (
          <Message key={`${m.time}-${i}`} msg={m} direct={direct} />
        ))}
        {trailing}
      </div>
      {!atBottom && (
        <button
          onClick={scrollToBottom}
          className="focusable absolute bottom-2 right-3 rounded-full border border-neutral-300 bg-white/90 px-2 py-0.5 text-[10px] font-medium shadow-sm dark:border-neutral-700 dark:bg-neutral-900/90"
        >
          New output ↓
        </button>
      )}
    </div>
  );
}
