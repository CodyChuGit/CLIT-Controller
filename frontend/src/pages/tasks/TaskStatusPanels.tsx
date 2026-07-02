import { useEffect, useRef, type ReactNode } from "react";
import StatusBadge from "../../components/StatusBadge";
import { StepChip } from "../../components/Markdown";
import TimelineCard from "../../components/TimelineCard";
import { Close, Spinner } from "../../components/icons";
import { formatDuration } from "../../lib/taskFormat";
import { cardFromTaskEvent } from "../../lib/displayModel";
import type { Approval, QueueState, TaskDetail, TaskEvent } from "../../types";
import { QUEUE_ACTIVE } from "./taskPageModel";

/* A single at-a-glance count in the State bar — a subtle pill so the numbers
   read as discrete metrics rather than a run-on sentence. */
function Metric({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "amber" | "violet";
}) {
  const text =
    tone === "amber"
      ? "text-amber-600 dark:text-amber-400"
      : tone === "violet"
        ? "text-violet-600 dark:text-violet-400"
        : "text-neutral-500 dark:text-neutral-400";
  return (
    <span
      className={`inline-flex items-center rounded-md bg-neutral-100/70 px-1.5 py-0.5 text-[11px] tabular-nums dark:bg-neutral-800/50 ${text}`}
    >
      {children}
    </span>
  );
}

export function HandoffLog({
  events,
  onOpenFile,
}: {
  events: TaskEvent[];
  onOpenFile: (name: string) => void;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [events.length]);

  if (events.length === 0) {
    return <p className="text-xs text-neutral-500">Nothing yet.</p>;
  }

  return (
    <div className="max-h-96 space-y-1.5 overflow-y-auto pr-1">
      {events.map((event, i) => (
        <TimelineCard
          key={`${event.time}-${i}`}
          card={cardFromTaskEvent(event, i)}
          density="compact"
          onOpenArtifact={onOpenFile}
        />
      ))}
      <div ref={endRef} />
    </div>
  );
}

export function QueueStrip({
  queue,
  onApprove,
  onRemove,
  onRetry,
  onSkip,
}: {
  queue: QueueState;
  onApprove: (id: string) => void;
  onRemove: (id: string) => void;
  onRetry: (id: string) => void;
  onSkip: (id: string) => void;
}) {
  const items = queue.items.filter(
    (item) => QUEUE_ACTIVE.includes(item.status) || item.status === "failed",
  );
  if (items.length === 0) return null;
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-2 border-b border-neutral-200 px-3 py-1.5 dark:border-neutral-800">
        <span className="section-title">Queue</span>
        <span className="chip">{items.length}</span>
      </div>
      {items.map((item) => (
        <div
          key={item.id}
          className="flex items-center gap-2 border-b border-neutral-100 px-3 py-2 last:border-0 dark:border-neutral-800/60"
        >
          {item.status === "running" ? (
            <Spinner className="h-3 w-3 shrink-0 text-blue-500" />
          ) : (
            <StatusBadge state={item.status} />
          )}
          <span className="text-xs font-medium">{item.label}</span>
          <span className="chip">{item.provider}</span>
          {item.note && (
            <span
              className="min-w-0 flex-1 truncate text-[11px] text-amber-600 dark:text-amber-400"
              title={item.note}
            >
              {item.note}
            </span>
          )}
          <span className="flex-1" />
          <div className="flex shrink-0 items-center gap-1">
            {(item.status === "blocked" || item.status === "awaiting_approval") && (
              <button className="btn-primary btn-xs" onClick={() => onApprove(item.id)}>
                Approve
              </button>
            )}
            {(item.status === "failed" ||
              item.status === "blocked" ||
              item.status === "cancelled") && (
              <button className="btn-secondary btn-xs" onClick={() => onRetry(item.id)}>
                Retry
              </button>
            )}
            {item.status !== "running" && item.status !== "skipped" && item.status !== "done" && (
              <button className="btn-secondary btn-xs" onClick={() => onSkip(item.id)}>
                Skip
              </button>
            )}
            {item.status !== "running" && (
              <button
                onClick={() => onRemove(item.id)}
                title="Remove"
                aria-label={`Remove ${item.label}`}
                className="focusable ml-0.5 cursor-pointer rounded p-1 text-neutral-400 hover:bg-neutral-100 hover:text-rose-600 dark:hover:bg-neutral-800 dark:hover:text-rose-400"
              >
                <Close className="h-3 w-3" />
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export function StateCard({
  detail,
  queue,
  approvals,
}: {
  detail: TaskDetail;
  queue: QueueState | null;
  approvals: Approval[];
}) {
  const task = detail.task;
  const items = (queue?.items ?? []).filter((item) => item.taskId === task.id);
  const queued = items.filter((item) => item.status === "queued").length;
  const blocked = items.filter((item) =>
    ["blocked", "awaiting_approval"].includes(item.status),
  ).length;
  const pendingApprovals = approvals.filter(
    (approval) => !approval.taskId || approval.taskId === task.id,
  ).length;
  const changed = new Set<string>();
  Object.values(task.steps).forEach((step) =>
    (step.codeChanged ?? []).forEach((file) => changed.add(file)),
  );
  const lastRun = [...(detail.runs ?? [])]
    .filter((run) => run.durationMs != null)
    .sort((a, b) => ((a.endedAt ?? "") < (b.endedAt ?? "") ? 1 : -1))[0];
  const current = task.fullSequence?.currentStep;

  return (
    <div className="card flex flex-wrap items-center gap-2 px-3 py-2 text-[11px]">
      <span className="section-title">State</span>
      <StatusBadge state={task.status} />
      {current && (
        <span className="inline-flex items-center gap-1 text-neutral-500">
          <span className="text-neutral-400">step</span>
          <StepChip name={current} />
        </span>
      )}
      <span className="flex-1" />
      {queued > 0 && <Metric>{queued} queued</Metric>}
      {blocked > 0 && <Metric tone="amber">{blocked} blocked</Metric>}
      {pendingApprovals > 0 && (
        <Metric tone="amber">
          {pendingApprovals} approval{pendingApprovals === 1 ? "" : "s"}
        </Metric>
      )}
      {changed.size > 0 && (
        <Metric tone="violet">
          {changed.size} file{changed.size === 1 ? "" : "s"} changed
        </Metric>
      )}
      {lastRun && formatDuration(lastRun.durationMs) && (
        <span className="font-mono text-[10px] text-neutral-400">
          last {formatDuration(lastRun.durationMs)}
        </span>
      )}
    </div>
  );
}
