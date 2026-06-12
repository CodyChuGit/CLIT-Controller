import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { ArrowRight, ChevronDown, ChevronRight, Close, FileIcon, Inbox, Spinner, StopSquare } from "../components/icons";
import RoutingRecommendationCard from "../components/RoutingRecommendationCard";
import StatusBadge from "../components/StatusBadge";
import UsageHealthBadge from "../components/UsageHealthBadge";
import type { Health, RunInfo, StepPreview, StepState, TaskDetail, TaskEvent, TaskMeta } from "../types";

const STEP_ORDER = ["codex_spec", "claude_implement", "gemini_qa", "codex_review", "claude_fix"];

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
};

function fmtDuration(ms?: number | null): string {
  if (ms === undefined || ms === null) return "";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 90_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms / 60_000)}m${Math.round((ms % 60_000) / 1000)}s`;
}

/* ------------------------------------------------ artifact chips (handoffs) */

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

/* ------------------------------------------------------------- agent lanes */

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
  taskId,
  onRun,
  onOpenFile,
}: {
  preview: StepPreview;
  state: StepState;
  run: RunInfo | undefined;
  taskId: string;
  onRun: () => void;
  onOpenFile: (name: string) => void;
}) {
  const [showOutput, setShowOutput] = useState(false);
  const [prompt, setPrompt] = useState<string | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
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

  const togglePrompt = async () => {
    if (!showPrompt && prompt === null) {
      const file = (run?.logFile ?? state.logFile)?.split("/").pop()?.replace(/\.log$/, ".prompt.txt") ?? state.promptFile;
      try {
        const res = file
          ? await api.taskFile(taskId, `logs/${file}`)
          : { content: preview.commandPreview };
        setPrompt(res.content);
      } catch {
        setPrompt(preview.commandPreview);
      }
    }
    setShowPrompt(!showPrompt);
  };

  return (
    <div className={`rounded-xl border bg-white p-2.5 shadow-sm dark:bg-neutral-900 ${border}`}>
      <div className="flex items-center gap-1.5">
        <span className="min-w-0 flex-1 truncate text-xs font-semibold">{preview.label}</span>
        {running && <Spinner className="h-3 w-3 text-blue-500" />}
        <StatusBadge state={state.status} />
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-1">
        <span className="text-[9px] uppercase tracking-wide text-neutral-400">reads</span>
        {preview.reads.map((r) => (
          <ArtifactChip key={r} name={r} onOpen={SPECIAL_ARTIFACTS[r] ? undefined : onOpenFile} />
        ))}
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-1">
        <span className="text-[9px] uppercase tracking-wide text-neutral-400">writes</span>
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
            ✓ code: {state.codeChanged?.length} file(s)
          </span>
        )}
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[10px] tabular-nums text-neutral-500">
        {run?.durationMs != null && <span>{fmtDuration(run.durationMs)}</span>}
        {run?.exitCode !== null && run?.exitCode !== undefined && <span>exit {run.exitCode}</span>}
        <span>~{(preview.promptChars / 1000).toFixed(1)}k chars</span>
        {!preview.providerInstalled && <span className="text-rose-500">CLI missing</span>}
      </div>

      <div className="mt-2 flex items-center gap-1.5">
        <button className="btn-primary px-2 py-0.5 text-[11px]" onClick={onRun} disabled={running}>
          {running ? "Running…" : "Run"}
        </button>
        <button className="btn-secondary px-2 py-0.5 text-[11px]" onClick={togglePrompt} aria-expanded={showPrompt}>
          Prompt
        </button>
        {run && (run.stdout || run.stderr) && (
          <button className="btn-secondary px-2 py-0.5 text-[11px]" onClick={() => setShowOutput(!showOutput)} aria-expanded={showOutput}>
            Output
          </button>
        )}
      </div>

      {showPrompt && prompt !== null && (
        <pre className="mono-block mt-2 max-h-44 whitespace-pre-wrap text-[10px]">{prompt}</pre>
      )}
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
      {/* lane headers — one per agent; each agent is reviewable */}
      <div className="grid gap-3" style={cols}>
        {lanes.map((provider) => {
          const roles = STEP_ORDER.filter((s) => detail.stepPreviews[s]?.provider === provider).map(
            (s) => detail.stepPreviews[s].label,
          );
          return (
            <div
              key={provider}
              className="flex items-center gap-2 rounded-xl border border-neutral-200 bg-neutral-50 px-2.5 py-2 dark:border-neutral-800 dark:bg-neutral-950"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate font-mono text-xs font-bold">{provider}</div>
                <div className="truncate text-[10px] text-neutral-400" title={roles.join(", ")}>
                  {roles.join(" · ")}
                </div>
              </div>
              <UsageHealthBadge value={(detail.recommendation.health[provider] as Health) ?? null} name={provider} />
              <button className="btn-secondary px-2 py-0.5 text-[11px]" onClick={() => onReview(provider)}>
                Review
              </button>
            </div>
          );
        })}
      </div>

      {/* step rows + handoff connectors */}
      {STEP_ORDER.map((step, i) => {
        const preview = detail.stepPreviews[step];
        if (!preview) return null;
        const lane = lanes.indexOf(preview.provider);
        const prev = i > 0 ? detail.stepPreviews[STEP_ORDER[i - 1]] : null;
        return (
          <div key={step}>
            {prev && (
              <div className="flex items-center justify-center gap-1.5 py-1.5" aria-hidden="true">
                <span className="font-mono text-[10px] text-neutral-400">{prev.provider}</span>
                <ArrowRight className="h-3 w-3 text-neutral-300 dark:text-neutral-600" />
                <span className="flex flex-wrap items-center gap-1">
                  {preview.reads.map((r) => (
                    <ArtifactChip key={r} name={r} onOpen={SPECIAL_ARTIFACTS[r] ? undefined : onOpenFile} />
                  ))}
                </span>
                <ArrowRight className="h-3 w-3 text-neutral-300 dark:text-neutral-600" />
                <span className="font-mono text-[10px] text-neutral-400">{preview.provider}</span>
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
                      taskId={detail.task.id}
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
        <h3 className="text-sm font-semibold">
          Agent review — <span className="font-mono">{provider}</span>
        </h3>
        <span className="text-xs text-neutral-400">{runs.length} run(s) in this task</span>
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
        <p className="text-xs text-neutral-500">
          This agent hasn't run yet in this task. Run one of its steps, then review the exact prompt it received
          and the output it produced here.
        </p>
      ) : (
        <div className="space-y-2">
          {[...runs].reverse().map((run) => (
            <div key={run.id} className="rounded-xl border border-neutral-200 p-2.5 dark:border-neutral-800">
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

/* ------------------------------------------------------------ handoff log */

function HandoffLog({ events, onOpenFile }: { events: TaskEvent[]; onOpenFile: (name: string) => void }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [events.length]);

  if (events.length === 0) {
    return <p className="text-xs text-neutral-500">No orchestration events yet — run a step to see the handoff story.</p>;
  }
  return (
    <div className="max-h-80 space-y-1.5 overflow-y-auto pr-1">
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

/* ---------------------------------------------------------------- the page */

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskMeta[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [taskFile, setTaskFile] = useState<{ name: string; content: string } | null>(null);
  const [reviewAgent, setReviewAgent] = useState<string | null>(null);
  const [showRouting, setShowRouting] = useState(false);
  const fileViewerRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<number | null>(null);

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
      if (list.length > 0) setSelectedId((cur) => cur ?? list[0].id);
    });
  }, [loadTasks]);

  useEffect(() => {
    if (selectedId) {
      setTaskFile(null);
      setReviewAgent(null);
      void loadDetail(selectedId);
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

  const createTask = async () => {
    setCreating(true);
    setError(null);
    try {
      const meta = await api.createTask(title.trim(), goal.trim());
      setTitle("");
      setGoal("");
      await loadTasks();
      setSelectedId(meta.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  };

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
      setNotice("Manual Approval mode: command preview generated; click Run on the step to execute.");
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

  const openFile = async (name: string) => {
    if (!selectedId) return;
    try {
      setTaskFile(await api.taskFile(selectedId, name));
      fileViewerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      setNotice(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="grid h-full grid-cols-[270px_1fr]">
      {/* Left: create + list */}
      <div className="overflow-y-auto border-r border-neutral-200 p-4 dark:border-neutral-800">
        <h1 className="mb-3 text-xl font-semibold">Tasks</h1>
        <div className="card space-y-2.5 p-3.5">
          <div>
            <label className="label">Title</label>
            <input className="input" value={title} placeholder="Fix playback overlay" onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <label className="label">User goal</label>
            <textarea
              className="input min-h-[80px] resize-y"
              value={goal}
              placeholder="Describe what should change…"
              onChange={(e) => setGoal(e.target.value)}
            />
          </div>
          <button className="btn-primary w-full justify-center" onClick={createTask} disabled={creating || !title.trim() || !goal.trim()}>
            {creating ? "Creating…" : "Create task"}
          </button>
        </div>

        <div className="mt-4 space-y-1.5">
          {tasks.map((t) => (
            <button
              key={t.id}
              onClick={() => setSelectedId(t.id)}
              aria-current={selectedId === t.id ? "true" : undefined}
              className={`focusable w-full cursor-pointer rounded-xl border px-3 py-2 text-left transition-colors duration-150 ${
                selectedId === t.id
                  ? "border-accent bg-blue-50 dark:border-accent dark:bg-blue-950/40"
                  : "border-neutral-200 bg-white hover:border-neutral-300 dark:border-neutral-800 dark:bg-neutral-900 dark:hover:border-neutral-700"
              }`}
            >
              <div className="truncate text-sm font-medium">{t.title}</div>
              <div className="mt-0.5 flex items-center gap-2">
                <StatusBadge state={t.status} />
                <span className="truncate font-mono text-[10px] text-neutral-400">{t.id}</span>
              </div>
            </button>
          ))}
          {tasks.length === 0 && !error && (
            <div className="flex flex-col items-center gap-1.5 px-1 pt-6 text-center">
              <Inbox className="h-5 w-5 text-neutral-300 dark:text-neutral-600" />
              <p className="text-xs text-neutral-500">No tasks yet — create one above.</p>
            </div>
          )}
        </div>
      </div>

      {/* Right: orchestration console */}
      <div className="space-y-4 overflow-y-auto p-5">
        {error && <div className="card border-rose-200 p-4 text-sm text-rose-600 dark:border-rose-900">{error}</div>}
        {!detail && !error && (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
            <Inbox className="h-7 w-7 text-neutral-300 dark:text-neutral-600" />
            <p className="text-sm text-neutral-500">Select a task on the left, or create one to get started.</p>
          </div>
        )}

        {detail && (
          <>
            <header className="flex flex-wrap items-center gap-2">
              <div className="min-w-0 flex-1">
                <h2 className="truncate text-lg font-semibold">{detail.task.title}</h2>
                <p className="truncate font-mono text-[11px] text-neutral-400">{detail.taskDir}</p>
              </div>
              <button className="btn-primary" onClick={runFull}>Run Full Sequence</button>
              <button className="btn-danger" onClick={stopAll}>
                <StopSquare className="h-3.5 w-3.5" /> Stop
              </button>
              <button className="btn-secondary" onClick={() => void api.openTaskFolder(detail.task.id)}>
                Open Folder
              </button>
            </header>

            <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500">
              {detail.task.fullSequence && detail.task.fullSequence.status !== "idle" && (
                <>
                  Sequence: <StatusBadge state={detail.task.fullSequence.status} />
                  {detail.task.fullSequence.currentStep && <span>at {detail.task.fullSequence.currentStep}</span>}
                </>
              )}
              <span className="flex-1" />
              <button
                className="focusable flex cursor-pointer items-center gap-1 rounded text-xs text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
                onClick={() => setShowRouting(!showRouting)}
                aria-expanded={showRouting}
              >
                {showRouting ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                Routing recommendation
                {detail.recommendation.cheaperRouteRecommended && (
                  <span className="rounded-full bg-emerald-100 px-1.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                    cheaper route
                  </span>
                )}
              </button>
            </div>

            {notice && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
                {notice}
              </div>
            )}
            {showRouting && <RoutingRecommendationCard rec={detail.recommendation} />}

            <FlowBoard detail={detail} onRun={(s) => void runStep(s)} onOpenFile={openFile} onReview={setReviewAgent} />

            {reviewAgent && <AgentReview provider={reviewAgent} detail={detail} onClose={() => setReviewAgent(null)} />}

            <section className="card p-4">
              <h3 className="mb-2 text-sm font-semibold">
                Handoff log <span className="font-normal text-neutral-400">— how work moves between agents</span>
              </h3>
              <HandoffLog events={detail.task.events ?? []} onOpenFile={openFile} />
            </section>

            <section className="card p-4" ref={fileViewerRef}>
              <h3 className="mb-2 text-sm font-semibold">Task files</h3>
              <div className="flex flex-wrap gap-1.5">
                {detail.files.map((f) => (
                  <button
                    key={f.name}
                    onClick={() => void openFile(f.name)}
                    className={`focusable cursor-pointer rounded-lg border px-2.5 py-1 font-mono text-[11px] transition-colors duration-150 ${
                      taskFile?.name === f.name
                        ? "border-accent bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300"
                        : "border-neutral-200 text-neutral-600 hover:border-neutral-300 dark:border-neutral-700 dark:text-neutral-400"
                    }`}
                  >
                    {f.name}
                  </button>
                ))}
              </div>
              {taskFile && (
                <div className="mt-3">
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
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}
