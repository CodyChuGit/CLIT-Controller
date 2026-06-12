import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Close, FileIcon, Folder, Inbox, Spinner, StopSquare } from "../components/icons";
import StatusBadge from "../components/StatusBadge";
import { loadState, saveState } from "../persist";
import type { QueueState, RunInfo, StepState, TaskDetail, TaskEvent, TaskMeta } from "../types";

const STEP_ORDER = ["codex_spec", "claude_implement", "gemini_qa", "codex_review", "claude_fix"];
const SHORT_LABELS: Record<string, string> = {
  codex_spec: "Spec",
  claude_implement: "Implement",
  gemini_qa: "QA",
  codex_review: "Review",
  claude_fix: "Fix",
};

const QUEUE_ACTIVE = ["queued", "awaiting_approval", "blocked", "running"];

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
  queued: "bg-neutral-400",
};

function fmtDuration(ms?: number | null): string {
  if (ms === undefined || ms === null) return "";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 90_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms / 60_000)}m${Math.round((ms % 60_000) / 1000)}s`;
}

function ArtifactChip({ name, onOpen }: { name: string; onOpen?: (name: string) => void }) {
  const special = SPECIAL_ARTIFACTS[name];
  if (special) {
    return (
      <span className="rounded border border-violet-200 bg-violet-50 px-1.5 py-0.5 font-mono text-[10px] text-violet-700 dark:border-violet-900 dark:bg-violet-950/40 dark:text-violet-300">
        {special}
      </span>
    );
  }
  return (
    <button
      onClick={() => onOpen?.(name)}
      disabled={!onOpen}
      title={onOpen ? `Open ${name}` : name}
      className={`focusable rounded border border-emerald-300 bg-emerald-50 px-1.5 py-0.5 font-mono text-[10px] text-emerald-700 transition-colors dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 ${
        onOpen ? "cursor-pointer hover:border-blue-400 hover:text-blue-600 dark:hover:text-blue-300" : ""
      }`}
    >
      {name.replace(".md", "")}
    </button>
  );
}

/* ----------------------------------------------------------- the flow chart */

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
  queued: { ring: "border-neutral-400", fill: "", mark: "·" },
  awaiting_approval: { ring: "border-amber-500", fill: "bg-amber-500/10", mark: "!" },
  blocked: { ring: "border-amber-500", fill: "bg-amber-500/10", mark: "!" },
  succeeded: { ring: "border-emerald-500", fill: "bg-emerald-500/10", mark: "✓" },
  failed: { ring: "border-rose-500", fill: "bg-rose-500/10", mark: "✕" },
  error: { ring: "border-rose-500", fill: "bg-rose-500/10", mark: "✕" },
  cancelled: { ring: "border-neutral-400", fill: "", mark: "–" },
  provider_missing: { ring: "border-amber-500", fill: "bg-amber-500/10", mark: "–" },
  skipped_budget: { ring: "border-amber-400", fill: "", mark: "–" },
};

/** One horizontal chain — only the steps this task actually uses light up.
 *  The orchestrator decides which: a task may be implement-only, spec-only, QA-only… */
function FlowChart({
  detail,
  queue,
  selected,
  onSelect,
}: {
  detail: TaskDetail;
  queue: QueueState | null;
  selected: string | null;
  onSelect: (step: string) => void;
}) {
  const overlay: Record<string, string> = {};
  for (const item of queue?.items ?? []) {
    if (item.taskId === detail.task.id && QUEUE_ACTIVE.includes(item.status)) {
      overlay[item.step] = item.status;
    }
  }

  return (
    <div className="card flex items-start justify-between gap-0 px-4 py-3">
      {STEP_ORDER.map((step, i) => {
        const preview = detail.stepPreviews[step];
        const state = (overlay[step] ?? detail.task.steps[step]?.status ?? "idle") as NodeState;
        const involved = state !== "idle";
        const style = NODE_STYLE[state];
        const isSelected = selected === step;
        return (
          <div key={step} className="flex flex-1 items-start">
            {i > 0 && (
              <div
                className={`mt-3.5 h-px flex-1 ${
                  involved ? "bg-neutral-300 dark:bg-neutral-600" : "bg-neutral-200 dark:bg-neutral-800"
                }`}
                aria-hidden="true"
              />
            )}
            <button
              onClick={() => onSelect(step)}
              title={`${preview?.label ?? step} — ${state.replace(/_/g, " ")}`}
              className="focusable group flex cursor-pointer flex-col items-center gap-1 rounded px-1.5"
            >
              <span
                className={`flex h-7 w-7 items-center justify-center rounded-full border-2 text-xs font-bold transition-all duration-150 ${
                  state === "running"
                    ? "border-blue-500 bg-blue-500/10"
                    : involved && style
                      ? `${style.ring} ${style.fill}`
                      : "border-neutral-200 dark:border-neutral-800"
                } ${isSelected ? "ring-2 ring-accent/60 ring-offset-1 dark:ring-offset-neutral-900" : ""}`}
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
                  involved ? "text-neutral-800 dark:text-neutral-200" : "text-neutral-300 dark:text-neutral-700"
                }`}
              >
                {SHORT_LABELS[step]}
              </span>
              <span
                className={`font-mono text-[9px] leading-none ${
                  involved ? "text-neutral-400" : "text-neutral-300 dark:text-neutral-700"
                }`}
              >
                {preview?.provider}
              </span>
            </button>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------ selected step detail */

function StepDetail({
  detail,
  step,
  onRun,
  onOpenFile,
  onReview,
}: {
  detail: TaskDetail;
  step: string;
  onRun: () => void;
  onOpenFile: (name: string) => void;
  onReview: (provider: string) => void;
}) {
  const [show, setShow] = useState<"prompt" | "output" | null>(null);
  const [prompt, setPrompt] = useState<string | null>(null);
  const preview = detail.stepPreviews[step];
  const state: StepState = detail.task.steps[step] ?? { status: "idle" };
  const runs = detail.runs.filter((r) => r.step === step);
  const run: RunInfo | undefined = runs[runs.length - 1];

  useEffect(() => {
    setShow(null);
    setPrompt(null);
  }, [step]);

  const togglePrompt = async () => {
    if (show === "prompt") return setShow(null);
    if (prompt === null) {
      const file = (run?.logFile ?? state.logFile)?.split("/").pop()?.replace(/\.log$/, ".prompt.txt") ?? state.promptFile;
      try {
        const res = file ? await api.taskFile(detail.task.id, `logs/${file}`) : { content: preview.commandPreview };
        setPrompt(res.content);
      } catch {
        setPrompt(preview.commandPreview);
      }
    }
    setShow("prompt");
  };

  if (!preview) return null;
  return (
    <div className="card px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold">{preview.label}</span>
        <button
          onClick={() => onReview(preview.provider)}
          title={`Review everything ${preview.provider} did in this task`}
          className="focusable chip cursor-pointer hover:text-blue-600 dark:hover:text-blue-400"
        >
          {preview.provider}
        </button>
        <StatusBadge state={state.status} />
        {run?.durationMs != null && (
          <span className="text-[10px] tabular-nums text-neutral-400">
            {fmtDuration(run.durationMs)} · exit {run.exitCode ?? "—"}
          </span>
        )}
        {(state.artifactsWritten ?? []).map((a) => (
          <ArtifactChip key={a} name={a} onOpen={onOpenFile} />
        ))}
        {(state.codeChanged?.length ?? 0) > 0 && (
          <span className="rounded border border-violet-300 bg-violet-50 px-1.5 py-0.5 font-mono text-[10px] text-violet-700 dark:border-violet-800 dark:bg-violet-950/40 dark:text-violet-300" title={state.codeChanged?.join("\n")}>
            code: {state.codeChanged?.length}
          </span>
        )}
        <span className="flex-1" />
        <button className="btn-secondary px-2 py-0.5 text-[11px]" onClick={togglePrompt}>
          {show === "prompt" ? "Hide" : "Prompt"}
        </button>
        {run && (run.stdout || run.stderr) && (
          <button
            className="btn-secondary px-2 py-0.5 text-[11px]"
            onClick={() => setShow(show === "output" ? null : "output")}
          >
            {show === "output" ? "Hide" : "Output"}
          </button>
        )}
        <button className="btn-primary px-2 py-0.5 text-[11px]" onClick={onRun} disabled={state.status === "running"}>
          {state.status === "running" ? "Running…" : "Run"}
        </button>
      </div>
      {show === "prompt" && prompt !== null && (
        <pre className="mono-block mt-2 max-h-48 whitespace-pre-wrap text-[10px]">{prompt}</pre>
      )}
      {show === "output" && run && (
        <pre className="mono-block mt-2 max-h-64 whitespace-pre-wrap text-[10px]">
          {run.stdout}
          {run.stderr && `\n--- stderr ---\n${run.stderr}`}
        </pre>
      )}
    </div>
  );
}

/* ------------------------------------------------------------ handoff log */

function HandoffLog({ events, onOpenFile }: { events: TaskEvent[]; onOpenFile: (name: string) => void }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [events.length]);

  if (events.length === 0) {
    return <p className="text-xs text-neutral-500">Nothing yet.</p>;
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
                  <ArtifactChip key={a} name={a} onOpen={onOpenFile} />
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

/* ------------------------------------------------------------ queue strip */

function QueueStrip({
  queue,
  onApprove,
  onRemove,
}: {
  queue: QueueState;
  onApprove: (id: string) => void;
  onRemove: (id: string) => void;
}) {
  const items = queue.items.filter((i) => QUEUE_ACTIVE.includes(i.status) || i.status === "failed");
  if (items.length === 0) return null;
  return (
    <div className="card overflow-hidden">
      {items.map((item) => (
        <div
          key={item.id}
          className="flex items-center gap-2 border-b border-neutral-100 px-3 py-1.5 last:border-0 dark:border-neutral-800/60"
        >
          {item.status === "running" ? <Spinner className="h-3 w-3 shrink-0 text-blue-500" /> : <StatusBadge state={item.status} />}
          <span className="text-xs font-medium">{item.label}</span>
          <span className="chip">{item.provider}</span>
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
          {item.status === "failed" && (
            <button className="btn-secondary px-2 py-0.5 text-[11px]" onClick={() => onApprove(item.id)}>
              Retry
            </button>
          )}
          {item.status !== "running" && (
            <button
              onClick={() => onRemove(item.id)}
              title="Remove"
              aria-label={`Remove ${item.label}`}
              className="focusable cursor-pointer rounded p-0.5 text-neutral-400 hover:text-rose-600 dark:hover:text-rose-400"
            >
              <Close className="h-3 w-3" />
            </button>
          )}
        </div>
      ))}
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
    if (open[run.id] === what) {
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
        <p className="text-xs text-neutral-500">No runs in this task yet.</p>
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
                  {open[run.id] === "prompt" ? "Hide" : "Prompt"}
                </button>
                <button className="btn-secondary px-2 py-0.5 text-[11px]" onClick={() => void toggle(run, "output")}>
                  {open[run.id] === "output" ? "Hide" : "Output"}
                </button>
              </div>
              {open[run.id] === "prompt" && (
                <pre className="mono-block mt-2 max-h-64 whitespace-pre-wrap text-[10px]">{prompts[run.id] ?? "loading…"}</pre>
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
  const [selectedStep, setSelectedStep] = useState<string | null>(null);
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

  useEffect(() => {
    void loadQueue();
    const id = window.setInterval(loadQueue, 3000);
    return () => window.clearInterval(id);
  }, [loadQueue]);

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

  // While the queue is executing, keep the selected task's detail fresh too.
  const queueBusy = (queue?.items ?? []).some((i) => i.status === "running");
  useEffect(() => {
    if (queueBusy && selectedId) void loadDetail(selectedId);
  }, [queueBusy, queue, selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

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
      setSelectedStep(null);
      void loadDetail(selectedId);
    } else {
      setDetail(null);
    }
  }, [selectedId, loadDetail]);

  // Default node selection: the running step, else the last one that did something.
  useEffect(() => {
    if (!detail || selectedStep) return;
    const states = detail.task.steps;
    const running = STEP_ORDER.find((s) => states[s]?.status === "running");
    const lastActive = [...STEP_ORDER].reverse().find((s) => states[s] && states[s].status !== "idle");
    setSelectedStep(running ?? lastActive ?? null);
  }, [detail, selectedStep]);

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
      setNotice("Not run — Claude is red.");
    } else if (res.status === "provider_missing") {
      setNotice(res.message ?? "Provider missing — prompt saved to the task folder.");
    } else if (res.status === "manual_preview") {
      setNotice("Manual Approval mode — click Run on a step to execute it.");
    } else if (res.status === "error") {
      setNotice(`Failed to start: ${res.message ?? "unknown error"}`);
    }
    await loadDetail(selectedId);
  };

  const runFull = async () => {
    if (!selectedId) return;
    setNotice(null);
    const res = await api.runFull(selectedId);
    if (res.status === "manual_preview") setNotice(res.message ?? "Manual approval mode.");
    else if (res.warning) setNotice(res.warning);
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
      <div className="mx-auto max-w-4xl space-y-3 p-6">
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
                  {t.title}
                </option>
              ))}
            </select>
          )}
          <span className="flex-1" />
          {detail && (
            <>
              <button className="btn-secondary" onClick={runFull}>Run all</button>
              <button className="btn-danger px-2" onClick={stopAll} title="Stop running processes" aria-label="Stop">
                <StopSquare className="h-3.5 w-3.5" />
              </button>
              <button
                className="btn-secondary px-2"
                onClick={() => void api.openTaskFolder(detail.task.id)}
                title="Open task folder"
                aria-label="Open task folder"
              >
                <Folder className="h-3.5 w-3.5" />
              </button>
            </>
          )}
        </header>

        {error && <div className="card border-rose-200 p-4 text-sm text-rose-600 dark:border-rose-900">{error}</div>}
        {notice && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
            {notice}
          </div>
        )}

        {tasks.length === 0 && !error && (
          <div className="flex flex-col items-center gap-2 py-24 text-center">
            <Inbox className="h-7 w-7 text-neutral-300 dark:text-neutral-600" />
            <p className="text-sm text-neutral-500">No tasks yet — ask the orchestrator.</p>
          </div>
        )}

        {detail && (
          <>
            <FlowChart detail={detail} queue={queue} selected={selectedStep} onSelect={setSelectedStep} />

            {selectedStep && (
              <StepDetail
                detail={detail}
                step={selectedStep}
                onRun={() => void runStep(selectedStep)}
                onOpenFile={openFile}
                onReview={setReviewAgent}
              />
            )}

            {queue && <QueueStrip queue={queue} onApprove={(id) => void approveItem(id)} onRemove={(id) => void removeItem(id)} />}

            {reviewAgent && <AgentReview provider={reviewAgent} detail={detail} onClose={() => setReviewAgent(null)} />}

            <section className="card p-4">
              <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                Orchestrator log
              </h2>
              <HandoffLog events={detail.task.events ?? []} onOpenFile={openFile} />
            </section>

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
