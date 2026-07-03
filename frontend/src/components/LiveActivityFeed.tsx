import { useEffect, useMemo, useRef } from "react";
import SmoothStreamingText from "./SmoothStreamingText";
import { Spinner } from "./icons";
import { parseLiveActivity, type ActivityItem } from "../lib/liveActivity";
import { useRunStream } from "../stream";

/* The live-activity feed: a run's raw CLI output rendered as a followable
   sequence of steps — narration, tool/command calls with status and a taste of
   their output, thinking sections — the way the Codex/Claude extensions show
   work in flight, instead of a "thinking…" label over a wall of log text.
   Presentation-only: input is the already-redacted accumulated stream text;
   the last item streams smoothly, finished items sit still. */

const STATUS_DOT: Record<string, string> = {
  ok: "bg-emerald-500",
  error: "bg-rose-500",
  running: "bg-neutral-400",
};

const MAX_ITEMS = 8;
const DONE_CLAMP = 280; // finished narration/thinking collapses to a taste

function clampText(text: string): string {
  return text.length > DONE_CLAMP ? `${text.slice(0, DONE_CLAMP)}…` : text;
}

function ActivityRow({ item, live }: { item: ActivityItem; live: boolean }) {
  if (item.kind === "meta") {
    return <div className="truncate font-mono text-[9px] text-neutral-400">{item.text}</div>;
  }
  if (item.kind === "tool") {
    return (
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          {item.status === "running" && live ? (
            <Spinner className="h-2.5 w-2.5 shrink-0 text-blue-500" />
          ) : (
            <span
              className={`h-1.5 w-1.5 shrink-0 rounded-full ${STATUS_DOT[item.status ?? "running"]}`}
              aria-hidden="true"
            />
          )}
          <code
            className="min-w-0 flex-1 truncate font-mono text-[10px] text-neutral-700 dark:text-neutral-300"
            title={item.label}
          >
            {item.label}
          </code>
        </div>
        {item.detail && (
          <div className="truncate pl-3 font-mono text-[9px] text-neutral-400" title={item.detail}>
            {item.detail.split("\n")[0]}
          </div>
        )}
      </div>
    );
  }
  const thinking = item.kind === "thinking";
  return (
    <div
      className={`whitespace-pre-wrap break-words text-[11px] leading-relaxed ${
        thinking ? "italic text-neutral-400" : "text-neutral-700 dark:text-neutral-200"
      }`}
    >
      {live ? (
        <SmoothStreamingText text={item.text} active mode="prose" maxChars={4000} />
      ) : (
        clampText(item.text)
      )}
    </div>
  );
}

export default function LiveActivityFeed({
  provider,
  stdout,
  stderr,
  active = true,
  className = "",
}: {
  provider: string | null | undefined;
  stdout: string;
  stderr: string;
  active?: boolean;
  className?: string;
}) {
  const items = useMemo(
    () => parseLiveActivity(provider, stdout, stderr),
    [provider, stdout, stderr],
  );
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight; // auto-tail as steps arrive
  }, [stdout, stderr]);

  if (items.length === 0) return null;
  const shown = items.slice(-MAX_ITEMS);
  const hidden = items.length - shown.length;

  return (
    <div
      ref={ref}
      className={`max-h-52 w-full overflow-auto rounded-lg border border-blue-200 bg-blue-50/50 px-2.5 py-2 dark:border-blue-900 dark:bg-blue-950/30 ${className}`}
    >
      <div className="space-y-1.5">
        {hidden > 0 && (
          <div className="text-[9px] text-neutral-400">
            … {hidden} earlier step{hidden === 1 ? "" : "s"}
          </div>
        )}
        {shown.map((item, i) => (
          <ActivityRow key={i} item={item} live={active && i === shown.length - 1} />
        ))}
      </div>
    </div>
  );
}

/** Feed for a run id, reading from the shared event store ONLY (streamStore owns
 *  SSE + the polling fallback, dedupe, cursor resume) — never polled snapshots. */
export function LiveRunActivity({
  runId,
  provider,
  className,
}: {
  runId: string | null | undefined;
  provider?: string | null;
  className?: string;
}) {
  const stream = useRunStream(runId);
  if (!stream) return null;
  return (
    <LiveActivityFeed
      provider={provider ?? stream.provider}
      stdout={stream.stdout}
      stderr={stream.stderr}
      active={stream.status === "running"}
      className={className}
    />
  );
}
