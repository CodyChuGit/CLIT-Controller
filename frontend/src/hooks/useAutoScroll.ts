import { useCallback, useEffect, useRef, useState } from "react";

/* Pillar 4 — consistent auto-scroll for every chat/output surface.
   Follow new output only while the user is near the bottom; if they scroll up to
   read, stop following and expose `atBottom=false` so the surface can show a
   "new output" affordance; resume following when they return to the bottom. */

const NEAR_BOTTOM_PX = 48;

/** Pure: is the scroll position within `threshold` px of the bottom? */
export function isNearBottom(
  scrollTop: number,
  scrollHeight: number,
  clientHeight: number,
  threshold: number = NEAR_BOTTOM_PX,
): boolean {
  return scrollHeight - scrollTop - clientHeight <= threshold;
}

export function useAutoScroll<T extends HTMLElement>(dep: unknown) {
  const ref = useRef<T | null>(null);
  const [atBottom, setAtBottom] = useState(true);

  const onScroll = useCallback(() => {
    const el = ref.current;
    if (el) setAtBottom(isNearBottom(el.scrollTop, el.scrollHeight, el.clientHeight));
  }, []);

  // Follow new content only when already near the bottom (don't yank the user
  // away from older content they're reading).
  useEffect(() => {
    const el = ref.current;
    if (el && atBottom) el.scrollTop = el.scrollHeight;
  }, [dep, atBottom]);

  const scrollToBottom = useCallback(() => {
    const el = ref.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
      setAtBottom(true);
    }
  }, []);

  return { ref, atBottom, onScroll, scrollToBottom };
}
