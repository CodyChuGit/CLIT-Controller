import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Inbox, Spinner } from "../components/icons";
import RoutingRecommendationCard from "../components/RoutingRecommendationCard";
import StatusBadge from "../components/StatusBadge";
import type { RunInfo, StepPreview, TaskDetail, TaskMeta } from "../types";

const STEP_ORDER = ["codex_spec", "claude_implement", "gemini_qa", "codex_review", "claude_fix"];

function StepRow({
  preview,
  state,
  run,
  onRun,
}: {
  preview: StepPreview;
  state: { status: string; exitCode?: number | null };
  run: RunInfo | undefined;
  onRun: () => void;
}) {
  const [showPreview, setShowPreview] = useState(false);
  const [showOutput, setShowOutput] = useState(false);
  const running = state.status === "running";

  return (
    <div className="rounded-xl border border-neutral-200 p-3 dark:border-neutral-800">
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-0 flex-1 truncate text-sm font-medium">{preview.label}</span>
        <span className="chip">{preview.provider}</span>
        {!preview.providerInstalled && <StatusBadge state="missing" label="CLI missing" />}
        <StatusBadge state={state.status} />
        <button className="btn-secondary" onClick={() => setShowPreview(!showPreview)} aria-expanded={showPreview}>
          Preview
        </button>
        <button className="btn-primary" onClick={onRun} disabled={running}>
          {running && <Spinner className="h-3.5 w-3.5" />}
          {running ? "Running…" : "Run"}
        </button>
      </div>
      {showPreview && (
        <div className="mt-2">
          <div className="label">Command preview · ~{preview.promptChars.toLocaleString()} prompt chars</div>
          <pre className="mono-block max-h-48 whitespace-pre-wrap">{preview.commandPreview}</pre>
        </div>
      )}
      {run && (run.stdout || run.stderr) && (
        <div className="mt-2">
          <button className="text-xs text-blue-600 hover:underline dark:text-blue-400" onClick={() => setShowOutput(!showOutput)}>
            {showOutput ? "Hide output" : `Show output (${run.status})`}
          </button>
          {showOutput && (
            <pre className="mono-block mt-1 max-h-72 whitespace-pre-wrap">
              {run.stdout}
              {run.stderr && `\n--- stderr ---\n${run.stderr}`}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

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
  const [logs, setLogs] = useState<{ name: string; size: number; content: string }[] | null>(null);
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
      setLogs(null);
      void loadDetail(selectedId);
    }
  }, [selectedId, loadDetail]);

  // Poll while anything is running.
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

  const refreshLogs = async () => {
    if (!selectedId) return;
    const res = await api.taskLogs(selectedId);
    setLogs(res.files);
  };

  const openFile = async (name: string) => {
    if (!selectedId) return;
    setTaskFile(await api.taskFile(selectedId, name));
  };

  const runFor = (step: string): RunInfo | undefined => {
    const runs = detail?.runs.filter((r) => r.step === step) ?? [];
    return runs.length > 0 ? runs[runs.length - 1] : undefined;
  };

  return (
    <div className="grid h-full grid-cols-[300px_1fr]">
      {/* Left: create + list */}
      <div className="overflow-y-auto border-r border-neutral-200 p-5 dark:border-neutral-800">
        <h1 className="mb-3 text-xl font-semibold">Tasks</h1>
        <div className="card space-y-2.5 p-4">
          <div>
            <label className="label">Title</label>
            <input className="input" value={title} placeholder="Fix playback overlay" onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <label className="label">User goal</label>
            <textarea
              className="input min-h-[88px] resize-y"
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
              className={`w-full rounded-xl border px-3 py-2.5 text-left transition-colors ${
                selectedId === t.id
                  ? "border-blue-500 bg-blue-50 dark:border-blue-600 dark:bg-blue-950/40"
                  : "border-neutral-200 bg-white hover:border-neutral-300 dark:border-neutral-800 dark:bg-neutral-900"
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

      {/* Right: detail */}
      <div className="space-y-4 overflow-y-auto p-6">
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
              <button className="btn-danger" onClick={stopAll}>Stop Current Process</button>
              <button className="btn-secondary" onClick={() => void api.openTaskFolder(detail.task.id)}>
                Open Task Folder
              </button>
              <button className="btn-secondary" onClick={refreshLogs}>Refresh Logs</button>
            </header>

            {detail.task.fullSequence && detail.task.fullSequence.status !== "idle" && (
              <div className="flex items-center gap-2 text-xs text-neutral-500">
                Full sequence: <StatusBadge state={detail.task.fullSequence.status} />
                {detail.task.fullSequence.currentStep && <span>at {detail.task.fullSequence.currentStep}</span>}
              </div>
            )}
            {notice && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
                {notice}
              </div>
            )}

            <RoutingRecommendationCard rec={detail.recommendation} />

            <section className="space-y-2">
              <h3 className="text-sm font-semibold">Steps</h3>
              {STEP_ORDER.map((step) => {
                const preview = detail.stepPreviews[step];
                if (!preview) return null;
                return (
                  <StepRow
                    key={step}
                    preview={preview}
                    state={detail.task.steps[step] ?? { status: "idle" }}
                    run={runFor(step)}
                    onRun={() => void runStep(step)}
                  />
                );
              })}
            </section>

            <section className="card p-4">
              <h3 className="mb-2 text-sm font-semibold">Task files</h3>
              <div className="flex flex-wrap gap-1.5">
                {detail.files.map((f) => (
                  <button
                    key={f.name}
                    onClick={() => void openFile(f.name)}
                    className={`rounded-lg border px-2.5 py-1 font-mono text-[11px] transition-colors ${
                      taskFile?.name === f.name
                        ? "border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300"
                        : "border-neutral-200 text-neutral-600 hover:border-neutral-300 dark:border-neutral-700 dark:text-neutral-400"
                    }`}
                  >
                    {f.name}
                  </button>
                ))}
              </div>
              {taskFile && <pre className="mono-block mt-3 max-h-80 whitespace-pre-wrap">{taskFile.content}</pre>}
            </section>

            {logs && (
              <section className="card p-4">
                <h3 className="mb-2 text-sm font-semibold">Saved logs</h3>
                {logs.length === 0 && <p className="text-xs text-neutral-400">No log files yet.</p>}
                {logs.map((l) => (
                  <details key={l.name} className="mb-2">
                    <summary className="cursor-pointer font-mono text-xs text-neutral-600 dark:text-neutral-400">
                      {l.name} ({(l.size / 1024).toFixed(1)} KB)
                    </summary>
                    <pre className="mono-block mt-1 max-h-72 whitespace-pre-wrap">{l.content}</pre>
                  </details>
                ))}
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
