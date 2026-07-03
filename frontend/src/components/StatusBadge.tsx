const COLORS: Record<string, string> = {
  green: "bg-emerald-500",
  ok: "bg-emerald-500",
  succeeded: "bg-emerald-500",
  completed: "bg-emerald-500",
  yellow: "bg-amber-500",
  warn: "bg-amber-500",
  running: "bg-blue-500 animate-pulse",
  needs_login: "bg-amber-500",
  red: "bg-rose-500",
  failed: "bg-rose-500",
  error: "bg-rose-500",
  missing: "bg-rose-400",
  cancelled: "bg-neutral-400",
  idle: "bg-neutral-300 dark:bg-neutral-600",
  unchecked: "bg-neutral-300 dark:bg-neutral-600",
  queued: "bg-neutral-400",
  awaiting_approval: "bg-amber-500",
  blocked: "bg-rose-500",
  done: "bg-emerald-500",
  skipped: "bg-amber-400",
};

// Short display copy for the widest states — pills sit in narrow lanes/rows,
// so terse labels beat literal state names ("succeeded" → "done"). The full
// state stays in the tooltip.
const LABELS: Record<string, string> = {
  succeeded: "done",
  completed: "done",
  awaiting_approval: "approval",
};

export default function StatusBadge({
  state,
  label,
  count,
}: {
  state: string;
  label?: string;
  /** Optional tally folded into the pill ("done · 3") so it can't wrap onto
   *  its own row as a separate chip. */
  count?: number;
}) {
  const dot = COLORS[state] ?? "bg-neutral-300 dark:bg-neutral-600";
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[11px] font-medium text-neutral-700 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-300"
      title={state.replace(/_/g, " ") + (count ? ` · ${count} artifacts` : "")}
    >
      <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden="true" />
      {label ?? LABELS[state] ?? state.replace(/_/g, " ")}
      {count != null && count > 0 && (
        <span className="font-mono text-[10px] tabular-nums text-violet-600 dark:text-violet-300">
          · {count}
        </span>
      )}
    </span>
  );
}
