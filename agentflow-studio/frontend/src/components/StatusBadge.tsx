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
};

export default function StatusBadge({ state, label }: { state: string; label?: string }) {
  const dot = COLORS[state] ?? "bg-neutral-300 dark:bg-neutral-600";
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-xs font-medium text-neutral-700 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-300">
      <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden="true" />
      {label ?? state.replace(/_/g, " ")}
    </span>
  );
}
