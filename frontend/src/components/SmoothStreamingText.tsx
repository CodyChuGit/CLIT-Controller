import { useEffect, useRef, useState } from "react";

/* Presentation-only smoothing for generated/received text. It consumes the
   already-redacted, already-accumulated text from the shared event store
   (useRunStream / LiveOutput / a chat surface) and reveals newly-appended
   characters over animation frames so output reads like a live CLI stream.

   It owns NO stream/chat/task state, opens NO network connection, and never
   calls EventSource or any API. See docs/streaming-renderer-decision.md. */

type SmoothStreamingTextProps = {
  /** Already-redacted accumulated text from the event store. */
  text: string;
  /** Animate while true; reveal instantly when false (e.g. finished runs). */
  active?: boolean;
  mode?: "prose" | "mono";
  /** Cap the displayed tail for live panes (full output stays in logs/expanders). */
  maxChars?: number;
  className?: string;
};

// ~0.5s hard catch-up at 60fps; small deltas reveal at a readable CLI pace.
const CATCHUP_FRAMES = 30;
const MIN_CHARS_PER_FRAME = 2;

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export default function SmoothStreamingText({
  text,
  active = true,
  mode = "mono",
  maxChars,
  className = "",
}: SmoothStreamingTextProps) {
  const reduce = prefersReducedMotion();
  // Snap to the full text on first mount — an existing backlog isn't "newly
  // generated", so only genuine appends after mount animate.
  const revealedRef = useRef(text.length);
  const prevTextRef = useRef(text);
  const rafRef = useRef<number | undefined>(undefined);
  const [, force] = useState(0);
  const rerender = () => force((n) => n + 1);

  useEffect(() => {
    const prev = prevTextRef.current;
    prevTextRef.current = text;

    const cancel = () => {
      if (rafRef.current !== undefined) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = undefined;
      }
    };

    // Reveal instantly when inactive, reduced-motion, or the text was replaced/
    // shrunk (new run, cleared, capped) — never animate backwards.
    if (!active || reduce || !text.startsWith(prev)) {
      cancel();
      revealedRef.current = text.length;
      rerender();
      return cancel;
    }

    // Appended: walk the revealed cursor up to the new length over frames.
    if (revealedRef.current > text.length) revealedRef.current = text.length;
    const tick = () => {
      const remaining = text.length - revealedRef.current;
      if (remaining <= 0) {
        rafRef.current = undefined;
        return;
      }
      const step = Math.max(MIN_CHARS_PER_FRAME, Math.ceil(remaining / CATCHUP_FRAMES));
      revealedRef.current = Math.min(text.length, revealedRef.current + step);
      rerender();
      rafRef.current = requestAnimationFrame(tick);
    };
    cancel();
    rafRef.current = requestAnimationFrame(tick);
    return cancel;
  }, [text, active, reduce]);

  let out = text.slice(0, revealedRef.current);
  if (maxChars && out.length > maxChars) out = out.slice(-maxChars);

  return (
    <span
      className={`${mode === "mono" ? "font-mono" : ""} ${className}`.trim()}
      style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}
    >
      {out}
    </span>
  );
}
