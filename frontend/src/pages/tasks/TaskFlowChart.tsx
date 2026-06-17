import { Fragment } from "react";
import { Spinner } from "../../components/icons";
import { QUEUE_ACTIVE, SHORT_LABELS, STEP_ORDER } from "./taskPageModel";
import type { QueueState, TaskDetail } from "../../types";

type NodeState =
  | "idle"
  | "queued"
  | "awaiting_approval"
  | "blocked"
  | "running"
  | "succeeded"
  | "failed"
  | "error"
  | "cancelled"
  | "provider_missing"
  | "skipped_budget";

const NODE_STYLE: Record<string, { ring: string; fill: string; mark: string }> = {
  queued: { ring: "border-neutral-400", fill: "", mark: "." },
  awaiting_approval: { ring: "border-amber-500", fill: "bg-amber-500/10", mark: "!" },
  blocked: { ring: "border-amber-500", fill: "bg-amber-500/10", mark: "!" },
  succeeded: { ring: "border-emerald-500", fill: "bg-emerald-500/10", mark: "+" },
  failed: { ring: "border-rose-500", fill: "bg-rose-500/10", mark: "x" },
  error: { ring: "border-rose-500", fill: "bg-rose-500/10", mark: "x" },
  cancelled: { ring: "border-neutral-400", fill: "", mark: "-" },
  provider_missing: { ring: "border-amber-500", fill: "bg-amber-500/10", mark: "-" },
  skipped_budget: { ring: "border-amber-400", fill: "", mark: "-" },
};

export default function TaskFlowChart({
  detail,
  queue,
  onSelect,
}: {
  detail: TaskDetail;
  queue: QueueState | null;
  onSelect: (step: string) => void;
}) {
  const overlay: Record<string, string> = {};
  for (const item of queue?.items ?? []) {
    if (item.taskId === detail.task.id && QUEUE_ACTIVE.includes(item.status)) {
      overlay[item.step] = item.status;
    }
  }

  return (
    <div className="card flex items-start px-4 py-3">
      {STEP_ORDER.map((step, i) => {
        const preview = detail.stepPreviews[step];
        const state = (overlay[step] ?? detail.task.steps[step]?.status ?? "idle") as NodeState;
        const involved = state !== "idle";
        const style = NODE_STYLE[state];
        return (
          <Fragment key={step}>
            {i > 0 && (
              <div
                className={`mt-3.5 h-px min-w-4 flex-1 ${
                  involved
                    ? "bg-neutral-300 dark:bg-neutral-600"
                    : "bg-neutral-200 dark:bg-neutral-800"
                }`}
                aria-hidden="true"
              />
            )}
            <button
              onClick={() => onSelect(step)}
              title={`${preview?.label ?? step} - ${state.replace(/_/g, " ")}`}
              className="focusable flex w-20 shrink-0 cursor-pointer flex-col items-center gap-1 rounded"
            >
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full border-2 text-xs font-bold transition-all duration-150 ${
                  state === "running"
                    ? "border-blue-500 bg-blue-500/10"
                    : involved && style
                      ? `${style.ring} ${style.fill}`
                      : "border-neutral-200 dark:border-neutral-800"
                }`}
              >
                {state === "running" ? (
                  <Spinner className="h-3.5 w-3.5 text-blue-500" />
                ) : involved && style ? (
                  <span
                    className={
                      state === "succeeded"
                        ? "text-emerald-600 dark:text-emerald-400"
                        : ["failed", "error"].includes(state)
                          ? "text-rose-600 dark:text-rose-400"
                          : "text-amber-600 dark:text-amber-400"
                    }
                  >
                    {style.mark}
                  </span>
                ) : null}
              </span>
              <span
                className={`text-[10px] font-medium leading-none ${
                  involved
                    ? "text-neutral-800 dark:text-neutral-200"
                    : "text-neutral-300 dark:text-neutral-700"
                }`}
              >
                {SHORT_LABELS[step]}
              </span>
              <span
                className={`max-w-full truncate font-mono text-[10px] leading-none ${
                  involved ? "text-neutral-400" : "text-neutral-300 dark:text-neutral-700"
                }`}
              >
                {preview?.provider}
              </span>
            </button>
          </Fragment>
        );
      })}
    </div>
  );
}
