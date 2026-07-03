import { LiveRunActivity } from "../../components/LiveActivityFeed";
import { StepChip } from "../../components/Markdown";
import StatusBadge from "../../components/StatusBadge";
import { ProviderMark } from "../../components/conversation/Message";
import { BeanMark, Spinner, Terminal } from "../../components/icons";
import { QUEUE_ACTIVE, STEP_ORDER, taskCommandRuns } from "./taskPageModel";
import type { Approval, QueueState, TaskDetail } from "../../types";

/* The dispatch map: the task laid out by provider lane — Controller, Codex,
   Claude, Antigravity, Local tools — so a user can tell which agent owns which
   piece of work, what is active, and what is blocked, without opening step
   cards (revamp Workstream 4). Replaces the linear TaskFlowChart. Active run
   text streams from the shared event store via useRunStream. */

const LANES: { id: string; label: string; role: string }[] = [
  { id: "controller", label: "Controller", role: "routing · verdicts" },
  { id: "codex", label: "Codex", role: "specs · plans · reviews" },
  { id: "claude", label: "Claude", role: "implementation · fixes" },
  { id: "antigravity", label: "Antigravity", role: "QA · broad checks" },
  { id: "local", label: "Local tools", role: "shell · git · tests" },
];

/** Live activity for one run from the shared event store only. */
function LaneLiveStream({ runId }: { runId: string | null | undefined }) {
  return <LiveRunActivity runId={runId} className="mt-1" />;
}

function laneStatusRank(status: string): number {
  if (status === "running") return 0;
  if (status === "blocked" || status === "awaiting_approval") return 1;
  if (status === "queued") return 2;
  return 3;
}

export default function TaskDispatchMap({
  detail,
  queue,
  approvals,
  onSelectStep,
}: {
  detail: TaskDetail;
  queue: QueueState | null;
  approvals: Approval[];
  onSelectStep: (step: string) => void;
}) {
  const task = detail.task;

  // Queue overlay: an active queue item's status beats the stale step state.
  const overlay: Record<string, { status: string; runId: string | null }> = {};
  for (const item of queue?.items ?? []) {
    if (item.taskId === task.id && QUEUE_ACTIVE.includes(item.status)) {
      overlay[item.step] = { status: item.status, runId: item.runId };
    }
  }

  const stepItems = STEP_ORDER.map((step) => {
    const state = task.steps[step];
    const status = overlay[step]?.status ?? state?.status ?? "idle";
    const run = detail.runs.find((r) => r.step === step && r.status === "running");
    return {
      step,
      provider: detail.stepPreviews[step]?.provider ?? "?",
      status,
      artifacts: (state?.artifactsWritten?.length ?? 0) + (state?.codeChanged?.length ?? 0),
      runId: run?.id ?? overlay[step]?.runId ?? null,
    };
  });

  const orchestrating = detail.runs.find((r) => r.step === "orchestrate" && r.status === "running");
  const pendingApprovals = approvals.filter(
    (a) => a.status === "pending" && (!a.taskId || a.taskId === task.id),
  );
  const verdict = [...(task.events ?? [])]
    .reverse()
    .find((e) => e.type === "done" || e.type === "needs_user");
  const commands = taskCommandRuns(detail).slice(-3);

  return (
    // auto-fit: lanes wrap to as many columns as actually fit (the dock can
    // take half the window) instead of cramming five 150px columns.
    <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-2">
      {LANES.map((lane) => {
        const items = stepItems
          .filter((s) => s.provider === lane.id)
          .sort((a, b) => laneStatusRank(a.status) - laneStatusRank(b.status));
        const active =
          lane.id === "controller"
            ? Boolean(orchestrating)
            : items.some((s) => s.status === "running");
        return (
          <div
            key={lane.id}
            className={`card flex min-w-0 flex-col p-2 ${active ? "border-blue-300 dark:border-blue-800" : ""}`}
          >
            <div className="flex items-center gap-1.5 border-b border-neutral-100 pb-1.5 dark:border-neutral-800/60">
              {lane.id === "controller" ? (
                <BeanMark className="h-3.5 w-3.5 shrink-0 text-accent-subtle" />
              ) : lane.id === "local" ? (
                <Terminal className="h-3.5 w-3.5 shrink-0 text-neutral-400" />
              ) : (
                <ProviderMark id={lane.id} className="h-3.5 w-3.5 shrink-0" />
              )}
              <span className="shrink-0 text-[11px] font-semibold">{lane.label}</span>
              {active && <Spinner className="h-3 w-3 shrink-0 text-blue-500" />}
              <span
                className="min-w-0 flex-1 truncate text-right text-[9px] text-neutral-400"
                title={lane.role}
              >
                {lane.role}
              </span>
            </div>

            <div className="mt-1.5 min-h-10 space-y-1.5">
              {lane.id === "controller" ? (
                <>
                  {orchestrating && (
                    <div className="text-[10px] text-neutral-600 dark:text-neutral-300">
                      <span className="inline-flex items-center gap-1">
                        <Spinner className="h-2.5 w-2.5 text-violet-500" /> deciding next step…
                      </span>
                      <LaneLiveStream runId={orchestrating.id} />
                    </div>
                  )}
                  {pendingApprovals.length > 0 && (
                    <div className="rounded border border-amber-200 bg-amber-50/70 px-1.5 py-1 text-[10px] text-amber-700 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300">
                      {pendingApprovals.length} approval{pendingApprovals.length === 1 ? "" : "s"}{" "}
                      waiting
                    </div>
                  )}
                  {verdict && (
                    <div
                      className="text-[10px] leading-snug text-neutral-500"
                      title={verdict.detail}
                    >
                      <StatusBadge state={verdict.type === "done" ? "done" : "needs_user"} />
                      {/* line-clamp needs a block box; on an inline span it does nothing */}
                      <div className="mt-0.5 line-clamp-2 break-words">{verdict.detail}</div>
                    </div>
                  )}
                  {(task.consults ?? 0) > 0 && (
                    <div className="text-[9px] text-neutral-400">
                      {task.consults} consult{task.consults === 1 ? "" : "s"}
                    </div>
                  )}
                  {!orchestrating && !verdict && pendingApprovals.length === 0 && (
                    <p className="text-[10px] text-neutral-400">idle</p>
                  )}
                </>
              ) : lane.id === "local" ? (
                commands.length === 0 ? (
                  <p className="text-[10px] text-neutral-400">no commands run</p>
                ) : (
                  commands.map((run) => (
                    <div key={run.id} className="min-w-0 text-[10px]">
                      <div className="flex items-center gap-1">
                        {run.status === "running" ? (
                          <Spinner className="h-2.5 w-2.5 text-blue-500" />
                        ) : (
                          <span
                            className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                              run.status === "succeeded" ? "bg-emerald-500" : "bg-rose-500"
                            }`}
                            aria-hidden="true"
                          />
                        )}
                        <code
                          className="truncate font-mono text-neutral-600 dark:text-neutral-300"
                          title={run.commandPreview}
                        >
                          {run.commandPreview}
                        </code>
                      </div>
                      {run.status === "running" && <LaneLiveStream runId={run.id} />}
                    </div>
                  ))
                )
              ) : items.length === 0 ? (
                <p className="text-[10px] text-neutral-400">no work routed here</p>
              ) : (
                items.map((s) => (
                  <div key={s.step} className="min-w-0">
                    {/* wrap, don't overflow — pills flow left and wrapped lines
                        stay left-aligned, so stacking reads as one clean
                        left-biased column (no left/right zigzag) */}
                    <button
                      onClick={() => onSelectStep(s.step)}
                      className="focusable flex w-full cursor-pointer flex-wrap items-center gap-x-1.5 gap-y-0.5 rounded px-0.5 py-0.5 text-left transition-colors hover:bg-neutral-100 dark:hover:bg-neutral-800/60"
                      title={`${s.step} — ${s.status.replace(/_/g, " ")}`}
                    >
                      {s.status === "running" && (
                        <Spinner className="h-3 w-3 shrink-0 text-blue-500" />
                      )}
                      <StepChip name={s.step} />
                      {/* artifact tally rides inside the status pill ("done · 3")
                          so it can't wrap onto a second row by itself */}
                      {s.status !== "idle" && s.status !== "running" && (
                        <StatusBadge state={s.status} count={s.artifacts} />
                      )}
                    </button>
                    {s.status === "running" && <LaneLiveStream runId={s.runId} />}
                  </div>
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
