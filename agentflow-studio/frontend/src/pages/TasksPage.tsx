import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { ArrowRight, Close, FileIcon, Inbox, Spinner, StopSquare } from "../components/icons";
import StatusBadge from "../components/StatusBadge";
import { loadState, saveState } from "../persist";
import type { QueueState, RunInfo, StepPreview, StepState, TaskDetail, TaskEvent, TaskMeta } from "../types";

const STEP_ORDER = ["codex_spec", "claude_implement", "gemini_qa", "codex_review", "claude_fix"];

/** What the orchestrator has cued up — the system dispatches each item to its agent. */
function QueuePanel({
  queue,
  onApprove,
  onRemove,
  onClear,
  onSelectTask,
}: {
  queue: QueueState;
  onApprove: (id: string) => void;
  onRemove: (id: string) => void;
  onClear: () => void;
  onSelectTask: (taskId: string) => void;
}) {
  return (
    <section className="card overflow-hidden">
      <div className="flex items-center gap-2 border-b border-neutral-200 px-3 py-1.5 dark:border-neutral-800">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
          Execution queue{queue.activeCount > 0 ? ` (${queue.activeCount} active)` : ""}
        </span>
        {queue.mode === "manual_approval" && (
          <span className="rounded bg-amber-100 px-1.5 text-[10px] font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
            manual approval
          </span>
        )}
        <span className="flex-1" />
        {queue.items.some((i) => i.status !== "running") && (
          <button
            onClick={onClear}
            title="Clear queue (running items survive)"
            aria-label="Clear queue"
            className="focusable cursor-pointer rounded p-1 text-neutral-400 transition-colors duration-150 hover:bg-neutral-200 hover:text-neutral-700 dark:hover:bg-neutral-700 dark:hover:text-neutral-200"
          >
            <Close className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {queue.items.length === 0 ? (
        <p className="px-3 py-2.5 text-xs text-neutral-500">
          Queue is empty — the orchestrator cues steps here (ask it in the chat), and the system runs them
          one per agent, in order.
        </p>
      ) : (
        queue.items.map((item) => (
          <div
            key={item.id}
            className="flex items-center gap-2 border-b border-neutral-100 px-3 py-1.5 last:border-0 dark:border-neutral-800/60"
          >
            {item.status === "running" ? (
              <Spinner className="h-3 w-3 shrink-0 text-blue-500" />
            ) : (
              <StatusBadge state={item.status} />
            )}
            <span className="text-xs font-medium">{item.label}</span>
            <span className="chip">{item.provider}</span>
            <button
              onClick={() => onSelectTask(item.taskId)}
              title={`Select task ${item.taskId}`}
              className="focusable min-w-0 cursor-pointer truncate rounded font-mono text-[10px] text-neutral-400 hover:text-blue-600 dark:hover:text-blue-400"
            >
              {item.taskId}
            </button>
            {item.note && (
              <span className="min-w-0 flex-1 truncate text-[10px] text-amber-600 dark:text-amber-400" title={item.note}>
                {item.note}
              </span>
            )}
            <span className="flex-1" />
            {(item.status === "blocked" || item.status === "awaiting_approval") && (
              <button className="btn-primary px-2 py-0.5 text-[11px]" onClick={() => onApprove(item.id)}>
                Approve
              </button>
            )}
            {(item.status === "failed" || item.status === "skipped") && (
              <button className="btn-secondary px-2 py-0.5 text-[11px]" onClick={() => onApprove(item.id)}>
                Retry
              </button>
            )}
            {item.status !== "running" && (
              <button
                onClick={() => onRemove(item.id)}
                title="Remove from queue"
                aria-label={`Remove ${item.label} from queue`}
                className="focusable cursor-pointer rounded p-0.5 text-neutral-400 hover:text-rose-600 dark:hover:text-rose-400"
              >
                <Close className="h-3 w-3" />
              </button>
            )}
          </div>
        ))
      )}
    </section>
  );
}

const SPECIAL_ARTIFACTS: Record<string, string> = {
  "@code": "production code",
  "@diff": "git diff",
  "@folder": "task folder",
};

const EVENT_DOT: Record<string, string> = {
  task_created: "bg-neutral-400",
  step_started: "bg-blue-500",
  step_finished: "bg-emerald-500",
  provider_missing: "bg-amber-500",
  skipped: "bg-amber-500",
  blocked: "bg-rose-500",
  local_check: "bg-neutral-400",
  sequence: "bg-blue-500",
  consult: "bg-violet-500",
  done: "bg-emerald-500",
  needs_user: "bg-amber-500",
};

function fmtDuration(ms?: number | null): string {
  if (ms === undefined || ms === null) return "";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 90_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms / 60_000)}m${Math.round((ms % 60_000) / 1000)}s`;
}

function ArtifactChip({
  name,
  written,
  onOpen,
}: {
  name: string;
  written?: boolean;
  onOpen?: (name: string) => void;
}) {
  const special = SPECIAL_ARTIFACTS[name];
  if (special) {
    return (
      <span className="rounded border border-violet-200 bg-violet-50 px-1.5 py-0.5 font-mono text-[10px] text-violet-700 dark:border-violet-900 dark:bg-violet-950/40 dark:text-violet-300">
        {special}
      </span>
    );
  }
  const base = written
    ? "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300"
    : "border-neutral-200 text-neutral-500 dark:border-neutral-700 dark:text-neutral-400";
  return (
    <button
      onClick={() => onOpen?.(name)}
      disabled={!onOpen}
      title={onOpen ? `Open ${name}` : name}
      className={`focusable rounded border px-1.5 py-0.5 font-mono text-[10px] transition-colors ${base} ${
        onOpen ? "cursor-pointer hover:border-blue-400 hover:text-blue-600 dark:hover:text-blue-300" : ""
      }`}
    >
      {written && "✓ "}
      {name.replace(".md", "")}
    </button>
  );
}

/* ------------------------------------------------------------ handoff log */

function HandoffLog({ events, onOpenFile }: { events: TaskEvent[]; onOpenFile: (name: string) => void }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [events.length]);

  if (events.length === 0) {
    return <p className="text-xs text-neutral-500">No orchestrator actions yet for this task.</p>;
  }
  return (
    <div className="max-h-96 space-y-1.5 overflow-y-auto pr-1">
      {events.map((e, i) => (
        <div key={i} className="flex items-start gap-2">
          <span
            className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
              e.type === "step_finished" && e.status && e.status !== "succeeded" ? "bg-rose-500" : EVENT_DOT[e.type] ?? "bg-neutral-400"
            }`}
            aria-hidden="true"
          />
          <span className="w-16 shrink-0 font-mono text-[10px] tabular-nums leading-5 text-neutral-400">
            {new Date(e.time).toLocaleTimeString()}
          </span>
          <div className="min-w-0 flex-1 text-xs leading-5 text-neutral-700 dark:text-neutral-300">
            {e.detail}
            {(e.artifacts?.length ?? 0) > 0 && (
              <span className="ml-1.5 inline-flex flex-wrap gap-1 align-middle">
                {e.artifacts!.map((a) => (
                  <ArtifactChip key={a} name={a} written onOpen={onOpenFile} />
                ))}
              </span>
            )}
          </div>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}

/* ------------------------------------------------------------- flow board */

function laneList(previews: Record<string, StepPreview>): string[] {
  const lanes: string[] = [];
  for (const step of STEP_ORDER) {
    const p = previews[step]?.provider;
    if (p && !lanes.includes(p)) lanes.push(p);
  }
  return lanes;
}

function StepCard({
  preview,
  state,
  run,
  onRun,
  onOpenFile,
}: {
  preview: StepPreview;
  state: StepState;
  run: RunInfo | undefined;
  onRun: () => void;
  onOpenFile: (name: string) => void;
}) {
  const [showOutput, setShowOutput] = useState(false);
  const running = state.status === "running";

  const border =
    state.status === "running"
      ? "border-blue-400 dark:border-blue-600"
      : state.status === "succeeded"
        ? "border-emerald-300 dark:border-emerald-800"
        : ["failed", "error"].includes(state.status)
          ? "border-rose-300 dark:border-rose-800"
          : ["provider_missing", "skipped_budget"].includes(state.status)
            ? "border-amber-300 dark:border-amber-800"
            : "border-neutral-200 dark:border-neutral-800";

  return (
    <div className={`rounded-lg border bg-white p-2.5 shadow-sm dark:bg-neutral-900 ${border}`}>
      <div className="flex items-center gap-1.5">
        <span className="min-w-0 flex-1 truncate text-xs font-semibold">{preview.label}</span>
        {running && <Spinner className="h-3 w-3 text-blue-500" />}
        <StatusBadge state={state.status} />
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-1">
        {preview.writes.map((w) => (
          <ArtifactChip
            key={w}
            name={w}
            written={state.artifactsWritten?.includes(w)}
            onOpen={SPECIAL_ARTIFACTS[w] ? undefined : onOpenFile}
          />
        ))}
        {(state.codeChanged?.length ?? 0) > 0 && (
          <span
            className="rounded border border-violet-300 bg-violet-50 px-1.5 py-0.5 font-mono text-[10px] text-violet-700 dark:border-violet-800 dark:bg-violet-950/40 dark:text-violet-300"
            title={state.codeChanged?.join("\n")}
          >
            ✓ code: {state.codeChanged?.length}
          </span>
        )}
      </div>

      <div className="mt-2 flex items-center gap-2">
        <button className="btn-secondary px-2 py-0.5 text-[11px]" onClick={onRun} disabled={running}>
          {running ? "Running…" : "Run"}
        </button>
        {run && (run.stdout || run.stderr) && (
          <button
            className="focusable cursor-pointer rounded text-[11px] text-blue-600 hover:underline dark:text-blue-400"
            onClick={() => setShowOutput(!showOutput)}
            aria-expanded={showOutput}
          >
            {showOutput ? "Hide output" : "Output"}
          </button>
        )}
        <span className="flex-1" />
        {run?.durationMs != null && (
          <span className="text-[10px] tabular-nums text-neutral-400">
            {fmtDuration(run.durationMs)} · exit {run.exitCode ?? "—"}
          </span>
        )}
      </div>

      {showOutput && run && (
        <pre className="mono-block mt-2 max-h-56 whitespace-pre-wrap text-[10px]">
          {run.stdout}
          {run.stderr && `\n--- stderr ---\n${run.stderr}`}
        </pre>
      )}
    </div>
  );
}

function FlowBoard({
  detail,
  onRun,
  onOpenFile,
  onReview,
}: {
  detail: TaskDetail;
  onRun: (step: string) => void;
  onOpenFile: (name: string) => void;
  onReview: (provider: string) => void;
}) {
  const lanes = laneList(detail.stepPreviews);
  const cols = { gridTemplateColumns: `repeat(${lanes.length}, minmax(0, 1fr))` };
  const runFor = (step: string): RunInfo | undefined => {
    const runs = detail.runs.filter((r) => r.step === step);
    return runs[runs.length - 1];
  };

  return (
    <div className="card p-3">
      <div className="grid gap-3" style={cols}>
        {lanes.map((provider) => (
          <div key={provider} className="flex items-center justify-between px-1">
            <span className="font-mono text-xs font-bold">{provider}</span>
            <button
              className="focusable cursor-pointer rounded text-[11px] text-blue-600 hover:underline dark:text-blue-400"
              onClick={() => onReview(provider)}
            >
              Review
            </button>
          </div>
        ))}
      </div>

      {STEP_ORDER.map((step, i) => {
        const preview = detail.stepPreviews[step];
        if (!preview) return null;
        const lane = lanes.indexOf(preview.provider);
        const prev = i > 0 ? detail.stepPreviews[STEP_ORDER[i - 1]] : null;
        return (
          <div key={step}>
            {prev && (
              <div className="flex items-center justify-center gap-1.5 py-1.5" aria-hidden="true">
                <ArrowRight className="h-3 w-3 text-neutral-300 dark:text-neutral-600" />
                <span className="flex flex-wrap items-center gap-1">
                  {preview.reads.map((r) => (
                    <ArtifactChip key={r} name={r} onOpen={SPECIAL_ARTIFACTS[r] ? undefined : onOpenFile} />
                  ))}
                </span>
                <ArrowRight className="h-3 w-3 text-neutral-300 dark:text-neutral-600" />
              </div>
            )}
            <div className="grid gap-3" style={cols}>
              {lanes.map((_, idx) => (
                <div key={idx}>
                  {idx === lane && (
                    <StepCard
                      preview={preview}
                      state={detail.task.steps[step] ?? { status: "idle" }}
                      run={runFor(step)}
                      onRun={() => onRun(step)}
                      onOpenFile={onOpenFile}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ----------------------------------------------------------- agent review */

function AgentReview({
  provider,
  detail,
  onClose,
}: {
  provider: string;
  detail: TaskDetail;
  onClose: () => void;
}) {
  const runs = detail.runs.filter((r) => r.provider === provider);
  const [open, setOpen] = useState<Record<string, "prompt" | "output" | null>>({});
  const [prompts, setPrompts] = useState<Record<string, string>>({});

  const toggle = async (run: RunInfo, what: "prompt" | "output") => {
    const cur = open[run.id];
    if (cur === what) {
      setOpen({ ...open, [run.id]: null });
      return;
    }
    if (what === "prompt" && !prompts[run.id]) {
      const file = run.logFile?.split("/").pop()?.replace(/\.log$/, ".prompt.txt");
      try {
        const res = file ? await api.taskFile(detail.task.id, `logs/${file}`) : { content: run.commandPreview };
        setPrompts((p) => ({ ...p, [run.id]: res.content }));
      } catch {
        setPrompts((p) => ({ ...p, [run.id]: run.commandPreview }));
      }
    }
    setOpen({ ...open, [run.id]: what });
  };

  return (
    <section className="card border-blue-200 p-4 dark:border-blue-900">
      <div className="mb-2 flex items-center gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
          Agent review — <span className="font-mono lowercase">{provider}</span>
        </h3>
        <span className="text-xs text-neutral-400">{runs.length} run(s)</span>
        <span className="flex-1" />
        <button
          onClick={onClose}
          aria-label="Close agent review"
          className="focusable cursor-pointer rounded p-1 text-neutral-400 hover:bg-neutral-200 hover:text-neutral-700 dark:hover:bg-neutral-700 dark:hover:text-neutral-200"
        >
          <Close className="h-3.5 w-3.5" />
        </button>
      </div>

      {runs.length === 0 ? (
        <p className="text-xs text-neutral-500">This agent hasn't run in this task yet.</p>
      ) : (
        <div className="space-y-2">
          {[...runs].reverse().map((run) => (
            <div key={run.id} className="rounded-lg border border-neutral-200 p-2.5 dark:border-neutral-800">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-medium">{run.step}</span>
                <StatusBadge state={run.status} />
                <span className="tabular-nums text-neutral-400">
                  {new Date(run.startedAt).toLocaleTimeString()} · {fmtDuration(run.durationMs)} · exit {run.exitCode ?? "—"}
                </span>
                <span className="flex-1" />
                <button className="btn-secondary px-2 py-0.5 text-[11px]" onClick={() => void toggle(run, "prompt")}>
                  {open[run.id] === "prompt" ? "Hide prompt" : "Prompt sent"}
                </button>
                <button className="btn-secondary px-2 py-0.5 text-[11px]" onClick={() => void toggle(run, "output")}>
                  {open[run.id] === "output" ? "Hide output" : "Output received"}
                </button>
              </div>
              {open[run.id] === "prompt" && (
                <pre className="mono-block mt-2 max-h-64 whitespace-pre-wrap text-[10px]">
                  {prompts[run.id] ?? "loading…"}
                </pre>
              )}
              {open[run.id] === "output" && (
                <pre className="mono-block mt-2 max-h-64 whitespace-pre-wrap text-[10px]">
                  {run.stdout || "(no stdout)"}
                  {run.stderr && `\n--- stderr ---\n${run.stderr}`}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/* ---------------------------------------------------------------- the page */

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskMeta[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [taskFile, setTaskFile] = useState<{ name: string; content: string } | null>(null);
  const [reviewAgent, setReviewAgent] = useState<string | null>(null);
  const [queue, setQueue] = useState<QueueState | null>(null);
  const fileViewerRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<number | null>(null);

  const loadQueue = useCallback(async () => {
    try {
      setQueue(await api.queue());
    } catch {
      /* no workspace or backend away */
    }
  }, []);

  // The dispatcher works in the background — keep the queue view live.
  useEffect(() => {
    void loadQueue();
    const id = window.setInterval(loadQueue, 3000);
    return () => window.clearInterval(id);
  }, [loadQueue]);

  // While the queue is executing, keep the selected task's detail fresh too.
  const queueBusy = (queue?.items ?? []).some((i) => i.status === "running");
  useEffect(() => {
    if (queueBusy && selectedId) void loadDetail(selectedId);
  }, [queueBusy, queue, selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadTasks = useCallback(async () => {
    try {
      const list = await api.tasks();
      setTasks(list);
      setError(null);
      return list;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return [];
    }
  }, []);

  const loadDetail = useCallback(async (id: string) => {
    try {
      setDetail(await api.task(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void loadTasks().then((list) => {
      if (list.length > 0) {
        const remembered = loadState<string | null>("lastTask", null);
        setSelectedId((cur) => cur ?? (remembered && list.some((t) => t.id === remembered) ? remembered : list[0].id));
      }
    });
  }, [loadTasks]);

  useEffect(() => {
    if (selectedId) {
      saveState("lastTask", selectedId);
      setTaskFile(null);
      setReviewAgent(null);
      void loadDetail(selectedId);
    } else {
      setDetail(null);
    }
  }, [selectedId, loadDetail]);

  const anythingRunning =
    detail !== null &&
    (detail.task.fullSequence?.status === "running" ||
      Object.values(detail.task.steps).some((s) => s.status === "running"));

  useEffect(() => {
    if (anythingRunning && selectedId) {
      pollRef.current = window.setInterval(() => void loadDetail(selectedId), 2500);
      return () => {
        if (pollRef.current) window.clearInterval(pollRef.current);
      };
    }
  }, [anythingRunning, selectedId, loadDetail]);

  // Tasks are created by the orchestrator (chat) — keep the list fresh.
  useEffect(() => {
    const id = window.setInterval(() => {
      void loadTasks().then((list) => {
        if (list.length > 0) setSelectedId((cur) => cur ?? list[0].id);
      });
    }, 10_000);
    return () => window.clearInterval(id);
  }, [loadTasks]);

  const runStep = async (step: string, confirm = false) => {
    if (!selectedId) return;
    setNotice(null);
    const res = await api.runStep(selectedId, step, confirm);
    if (res.status === "needs_confirmation" && res.warning) {
      if (window.confirm(res.warning)) return runStep(step, true);
      setNotice("Step not run — Claude is red and the run was not confirmed.");
    } else if (res.status === "provider_missing") {
      setNotice(res.message ?? "Provider missing — prompt saved to the task folder.");
    } else if (res.status === "manual_preview") {
      setNotice("Manual Approval mode: nothing runs automatically — click Run on a step to execute it.");
    } else if (res.status === "error") {
      setNotice(`Failed to start: ${res.message ?? "unknown error"}`);
    }
    await loadDetail(selectedId);
  };

  const runFull = async () => {
    if (!selectedId) return;
    setNotice(null);
    const res = await api.runFull(selectedId);
    if (res.status === "manual_preview") {
      setNotice(res.message ?? "Manual approval mode — run steps individually.");
    } else if (res.warning) {
      setNotice(res.warning);
    }
    await loadDetail(selectedId);
  };

  const stopAll = async () => {
    const res = await api.stop();
    setNotice(res.stopped.length > 0 ? `Stopped ${res.stopped.length} process(es).` : "Nothing was running.");
    if (selectedId) await loadDetail(selectedId);
  };

  const approveItem = async (id: string) => {
    const res = await api.queueApprove(id);
    if (res.status !== "started") setNotice(res.message ?? res.status);
    setQueue(res.queue);
  };

  const removeItem = async (id: string) => setQueue(await api.queueRemove(id));
  const clearQueue = async () => setQueue(await api.queueClear());

  const openFile = async (name: string) => {
    if (!selectedId) return;
    try {
      setTaskFile(await api.taskFile(selectedId, name));
      fileViewerRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (e) {
      setNotice(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-4 p-6">
        <header className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold">Tasks</h1>
          {tasks.length > 0 && (
            <select
              className="input w-auto min-w-0 max-w-md flex-1 font-mono text-xs"
              value={selectedId ?? ""}
              onChange={(e) => setSelectedId(e.target.value)}
              aria-label="Select task"
            >
              {tasks.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title} — {t.id}
                </option>
              ))}
            </select>
          )}
          <span className="flex-1" />
          {detail && (
            <>
              <button className="btn-secondary" onClick={runFull}>Run Full Sequence</button>
              <button className="btn-danger" onClick={stopAll} title="Stop running processes" aria-label="Stop running processes">
                <StopSquare className="h-3.5 w-3.5" />
              </button>
              <button className="btn-secondary" onClick={() => void api.openTaskFolder(detail.task.id)}>
                Folder
              </button>
            </>
          )}
        </header>

        {detail && (detail.task.orchestrated || (detail.task.fullSequence && detail.task.fullSequence.status !== "idle")) && (
          <div className="flex items-center gap-2 text-xs text-neutral-500">
            {detail.task.orchestrated && (
              <span className="rounded bg-violet-100 px-1.5 text-[10px] font-medium text-violet-700 dark:bg-violet-950 dark:text-violet-300">
                orchestrator-driven
              </span>
            )}
            {detail.task.fullSequence && detail.task.fullSequence.status !== "idle" && (
              <>
                Sequence: <StatusBadge state={detail.task.fullSequence.status} />
                {detail.task.fullSequence.currentStep && <span>at {detail.task.fullSequence.currentStep}</span>}
              </>
            )}
          </div>
        )}
        {error && <div className="card border-rose-200 p-4 text-sm text-rose-600 dark:border-rose-900">{error}</div>}
        {notice && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
            {notice}
          </div>
        )}

        {queue && (
          <QueuePanel
            queue={queue}
            onApprove={(id) => void approveItem(id)}
            onRemove={(id) => void removeItem(id)}
            onClear={() => void clearQueue()}
            onSelectTask={setSelectedId}
          />
        )}

        {tasks.length === 0 && !error && (
          <div className="flex flex-col items-center gap-2 py-24 text-center">
            <Inbox className="h-7 w-7 text-neutral-300 dark:text-neutral-600" />
            <p className="text-sm text-neutral-500">No tasks yet.</p>
            <p className="max-w-sm text-xs text-neutral-400">
              Ask the orchestrator in the chat to create one — it will scaffold the task folder and it shows up
              here for review.
            </p>
          </div>
        )}

        {detail && (
          <>
            <section className="card p-4">
              <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Orchestrator log</h2>
              <HandoffLog events={detail.task.events ?? []} onOpenFile={openFile} />
            </section>

            <FlowBoard detail={detail} onRun={(s) => void runStep(s)} onOpenFile={openFile} onReview={setReviewAgent} />

            {reviewAgent && <AgentReview provider={reviewAgent} detail={detail} onClose={() => setReviewAgent(null)} />}

            {taskFile && (
              <section className="card p-4" ref={fileViewerRef}>
                <div className="mb-1 flex items-center justify-between">
                  <span className="flex items-center gap-1.5 font-mono text-[11px] text-neutral-500">
                    <FileIcon className="h-3 w-3" /> {taskFile.name}
                  </span>
                  <button
                    onClick={() => setTaskFile(null)}
                    aria-label="Close file viewer"
                    className="focusable cursor-pointer rounded p-0.5 text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200"
                  >
                    <Close className="h-3 w-3" />
                  </button>
                </div>
                <pre className="mono-block max-h-80 whitespace-pre-wrap">{taskFile.content}</pre>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
