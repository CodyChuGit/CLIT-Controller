import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { Close, FileIcon, Folder, Inbox, StopSquare } from "../components/icons";
import StatusBadge from "../components/StatusBadge";
import { ApprovalCard, CommandCard, ContextSummary } from "../components/TaskViews";
import TimelineCard from "../components/TimelineCard";
import RawDetail from "../components/RawDetail";
import { ComposerChip } from "../components/Composer";
import InputComposer from "../components/input/InputComposer";
import { Card, EmptyState } from "../components/ui";
import { useStructuralRevision } from "../stream";
import { loadState, saveState } from "../persist";
import TaskFlowChart from "./tasks/TaskFlowChart";
import StepChat from "./tasks/StepChat";
import { HandoffLog, QueueStrip, StateCard } from "./tasks/TaskStatusPanels";
import {
  STEP_ORDER,
  buildFinalCard,
  collectBudgetContext,
  taskChangedFiles,
  taskCommandRuns,
  taskFileKind,
} from "./tasks/taskPageModel";
import type { Approval, Exchange, QueueState, TaskDetail, TaskMeta } from "../types";

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskMeta[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [exchanges, setExchanges] = useState<Record<string, Exchange[]>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [taskFile, setTaskFile] = useState<{ name: string; content: string } | null>(null);
  const [diffFile, setDiffFile] = useState<{ name: string; diff: string } | null>(null);
  const [queue, setQueue] = useState<QueueState | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const streamRev = useStructuralRevision();
  const fileViewerRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<number | null>(null);

  const loadQueue = useCallback(async () => {
    try {
      const [q, appr] = await Promise.all([
        api.queue(),
        api.approvals(true).catch(() => ({ approvals: [] as Approval[] })),
      ]);
      setQueue(q);
      setApprovals(appr.approvals);
    } catch {
      /* no workspace or backend away */
    }
  }, []);

  useEffect(() => {
    void loadQueue();
    const id = window.setInterval(loadQueue, 3000);
    return () => window.clearInterval(id);
  }, [loadQueue, streamRev]);

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
      const [d, ex] = await Promise.all([api.task(id), api.taskExchanges(id)]);
      setDetail(d);
      setExchanges(ex.steps);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const queueBusy = (queue?.items ?? []).some((item) => item.status === "running");
  useEffect(() => {
    if (queueBusy && selectedId) void loadDetail(selectedId);
  }, [queueBusy, selectedId, loadDetail]);

  useEffect(() => {
    if (selectedId) void loadDetail(selectedId);
  }, [streamRev, selectedId, loadDetail]);

  useEffect(() => {
    void loadTasks().then((list) => {
      if (list.length > 0) {
        const remembered = loadState<string | null>("lastTask", null);
        setSelectedId(
          (cur) =>
            cur ??
            (remembered && list.some((task) => task.id === remembered) ? remembered : list[0].id),
        );
      }
    });
  }, [loadTasks]);

  useEffect(() => {
    if (selectedId) {
      saveState("lastTask", selectedId);
      setTaskFile(null);
      setDiffFile(null);
      void loadDetail(selectedId);
    } else {
      setDetail(null);
      setExchanges({});
    }
  }, [selectedId, loadDetail]);

  const anythingRunning =
    detail !== null &&
    (detail.task.fullSequence?.status === "running" ||
      Object.values(detail.task.steps).some((step) => step.status === "running"));

  useEffect(() => {
    if (!anythingRunning || !selectedId) return;
    pollRef.current = window.setInterval(() => void loadDetail(selectedId), 2500);
    return () => {
      if (pollRef.current !== null) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [anythingRunning, selectedId, loadDetail]);

  useEffect(() => {
    const id = window.setInterval(() => {
      void loadTasks().then((list) => {
        if (list.length > 0) setSelectedId((cur) => cur ?? list[0].id);
      });
    }, 10_000);
    return () => window.clearInterval(id);
  }, [loadTasks]);

  const budgetContext = useMemo(() => collectBudgetContext(exchanges), [exchanges]);
  const commandRuns = useMemo(() => taskCommandRuns(detail), [detail]);
  const finalCard = useMemo(() => buildFinalCard(detail), [detail]);
  const changedFiles = useMemo(() => taskChangedFiles(detail), [detail]);

  const runStep = async (step: string, confirm = false) => {
    if (!selectedId) return;
    setNotice(null);
    const res = await api.runStep(selectedId, step, confirm);
    if (res.status === "needs_confirmation" && res.warning) {
      if (window.confirm(res.warning)) return runStep(step, true);
      setNotice("Not run - Claude is red.");
    } else if (res.status === "provider_missing") {
      setNotice(res.message ?? "Provider missing - prompt saved to the task folder.");
    } else if (res.status === "manual_preview") {
      setNotice("Manual Approval mode - click Run on a step to execute it.");
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
    setNotice(
      res.stopped.length > 0
        ? `Stopped ${res.stopped.length} process(es).`
        : "Nothing was running.",
    );
    if (selectedId) await loadDetail(selectedId);
  };

  const approveItem = async (id: string) => {
    const res = await api.queueApprove(id);
    if (res.status !== "started") setNotice(res.message ?? res.status);
    setQueue(res.queue);
  };

  const resolveApproval = async (id: string, approve: boolean) => {
    try {
      await (approve ? api.approvalApprove(id) : api.approvalReject(id));
    } catch (e) {
      setNotice(e instanceof Error ? e.message : String(e));
    }
    await loadQueue();
    if (selectedId) await loadDetail(selectedId);
  };

  const removeItem = async (id: string) => setQueue(await api.queueRemove(id));

  const retryItem = async (id: string) => {
    const res = await api.queueRetry(id);
    if (res.status !== "ok") setNotice(res.message ?? res.status);
    setQueue(res);
  };

  const skipItem = async (id: string) => {
    const res = await api.queueSkip(id);
    if (res.status !== "ok") setNotice(res.message ?? res.status);
    setQueue(res);
  };

  const openFile = async (name: string) => {
    if (!selectedId) return;
    try {
      setTaskFile(await api.taskFile(selectedId, name));
      setDiffFile(null);
      fileViewerRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (e) {
      setNotice(e instanceof Error ? e.message : String(e));
    }
  };

  const openDiff = async (path: string) => {
    try {
      const d = await api.gitFileDiff(path, false);
      setDiffFile({
        name: path,
        diff: d.diff?.trim() ? d.diff : "(no diff - file may be unchanged)",
      });
      setTaskFile(null);
      fileViewerRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (e) {
      setNotice(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-3 p-6 pt-0">
        <header className="sticky top-0 z-10 -mx-6 space-y-1.5 border-b border-neutral-200 bg-surface px-6 pb-2.5 pt-5 dark:border-neutral-800 dark:bg-neutral-950">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold">Tasks</h1>
            {tasks.length > 0 && (
              <select
                className="select min-w-0 max-w-md flex-1 font-mono"
                value={selectedId ?? ""}
                onChange={(e) => setSelectedId(e.target.value)}
                aria-label="Select task"
              >
                {tasks.map((task) => (
                  <option key={task.id} value={task.id}>
                    {task.title}
                  </option>
                ))}
              </select>
            )}
            <span className="flex-1" />
            {detail && (
              <>
                <button className="btn-secondary" onClick={runFull}>
                  Run all
                </button>
                <button
                  className="btn-danger px-2"
                  onClick={stopAll}
                  title="Stop running processes"
                  aria-label="Stop"
                >
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
          </div>
          {detail && (
            <div className="flex items-center gap-2 text-xs">
              <StatusBadge state={detail.task.status} />
              <p className="min-w-0 flex-1 truncate text-neutral-500" title={detail.task.goal}>
                {detail.task.goal}
              </p>
            </div>
          )}
        </header>

        {error && (
          <div className="card border-rose-200 p-4 text-sm text-rose-600 dark:border-rose-900">
            {error}
          </div>
        )}
        {notice && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
            {notice}
          </div>
        )}

        {tasks.length === 0 && !error && (
          <EmptyState icon={<Inbox />} message="No tasks yet - ask the controller." />
        )}

        {detail && (
          <>
            <TaskFlowChart
              detail={detail}
              queue={queue}
              onSelect={(step) =>
                document
                  .getElementById(`step-${step}`)
                  ?.scrollIntoView({ behavior: "smooth", block: "center" })
              }
            />

            <StateCard detail={detail} queue={queue} approvals={approvals} />

            {finalCard && (
              <TimelineCard card={finalCard} density="detailed" onOpenArtifact={openFile} />
            )}

            {queue && (
              <QueueStrip
                queue={queue}
                onApprove={(id) => void approveItem(id)}
                onRemove={(id) => void removeItem(id)}
                onRetry={(id) => void retryItem(id)}
                onSkip={(id) => void skipItem(id)}
              />
            )}

            {approvals.filter((approval) => !approval.taskId || approval.taskId === detail.task.id)
              .length > 0 && (
              <div className="space-y-2">
                {approvals
                  .filter((approval) => !approval.taskId || approval.taskId === detail.task.id)
                  .map((approval) => (
                    <ApprovalCard
                      key={approval.id}
                      approval={approval}
                      onApprove={(id) => void resolveApproval(id, true)}
                      onReject={(id) => void resolveApproval(id, false)}
                    />
                  ))}
              </div>
            )}

            <Card title="Continue task" pad>
              <InputComposer
                workspaceId="workspace"
                destination={{ kind: "task", taskId: detail.task.id, intent: "continue" }}
                submitMode="continue"
                placeholder="Tell the controller what to do next for this task..."
                onResult={(res) => {
                  if (["error", "busy", "provider_missing", "claude_red"].includes(res.status)) {
                    setNotice(res.message ?? res.status);
                  } else {
                    setNotice(
                      "Sent — the reply streams in the controller dock, scoped to this task.",
                    );
                  }
                }}
                contextChips={
                  <>
                    <ComposerChip mono title="Task">
                      {detail.task.id}
                    </ComposerChip>
                    <StatusBadge state={detail.task.status} />
                  </>
                }
              />
            </Card>

            {budgetContext && (
              <ContextSummary budget={budgetContext.budget} repeated={budgetContext.repeated} />
            )}

            <div className="grid gap-3 md:grid-cols-2">
              {STEP_ORDER.map((step, i) => (
                <div key={step} className={i === STEP_ORDER.length - 1 ? "md:col-span-2" : ""}>
                  <StepChat
                    detail={detail}
                    step={step}
                    exchanges={exchanges[step] ?? []}
                    onRun={() => void runStep(step)}
                    onOpenFile={openFile}
                  />
                </div>
              ))}
            </div>

            {changedFiles.length > 0 && (
              <div className="card border-l-2 border-l-violet-400 p-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-violet-500" aria-hidden="true" />
                  <span className="text-xs font-semibold">Diff</span>
                  <span className="chip">
                    {changedFiles.length} file{changedFiles.length === 1 ? "" : "s"}
                  </span>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {changedFiles.map((file) => (
                    <button
                      key={file}
                      onClick={() => void openDiff(file)}
                      title={`Diff ${file}`}
                      className="focusable rounded border border-violet-200 bg-violet-50 px-1.5 py-0.5 font-mono text-[10px] text-violet-700 transition-colors hover:border-blue-400 hover:text-blue-600 dark:border-violet-900 dark:bg-violet-950/40 dark:text-violet-300 dark:hover:text-blue-300"
                    >
                      {file.split("/").pop()}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {commandRuns.length > 0 && (
              <Card title="Commands" pad bodyClassName="space-y-2">
                {commandRuns.map((run) => (
                  <CommandCard key={run.id} run={run} />
                ))}
              </Card>
            )}

            <Card title="Controller log" pad>
              <HandoffLog events={detail.task.events ?? []} onOpenFile={openFile} />
            </Card>

            {(detail.task.events ?? []).length > 0 && (
              <Card title="Events" pad>
                <RawDetail
                  text={(detail.task.events ?? [])
                    .map(
                      (event) =>
                        `${new Date(event.time).toLocaleTimeString()}  ${event.type}` +
                        `${event.step ? ` ${event.step}` : ""}${event.provider ? ` ${event.provider}` : ""}  ${event.detail}`,
                    )
                    .join("\n")}
                  label="durable events"
                  kind="events"
                  pageSize={50}
                />
              </Card>
            )}

            {taskFile && (
              <div ref={fileViewerRef}>
                <Card
                  title={
                    <span className="flex min-w-0 items-center gap-1.5 font-mono text-[11px] text-neutral-500">
                      <FileIcon className="h-3 w-3 shrink-0" />{" "}
                      <span className="truncate">{taskFile.name}</span>
                    </span>
                  }
                  actions={
                    <button
                      onClick={() => setTaskFile(null)}
                      aria-label="Close file viewer"
                      className="icon-btn"
                    >
                      <Close className="h-3 w-3" />
                    </button>
                  }
                >
                  <RawDetail
                    text={taskFile.content}
                    label={taskFile.name}
                    kind={taskFileKind(taskFile.name)}
                    pageSize={100}
                    className="border-0"
                  />
                </Card>
              </div>
            )}

            {diffFile && (
              <div ref={fileViewerRef}>
                <Card
                  title={
                    <span className="flex min-w-0 items-center gap-1.5 font-mono text-[11px] text-neutral-500">
                      <FileIcon className="h-3 w-3 shrink-0" />{" "}
                      <span className="truncate">{diffFile.name}</span>
                      <span className="text-neutral-400">- diff</span>
                    </span>
                  }
                  actions={
                    <button
                      onClick={() => setDiffFile(null)}
                      aria-label="Close diff viewer"
                      className="icon-btn"
                    >
                      <Close className="h-3 w-3" />
                    </button>
                  }
                >
                  <RawDetail
                    text={diffFile.diff}
                    label={`${diffFile.name} diff`}
                    kind="diff"
                    pageSize={100}
                    className="border-0"
                  />
                </Card>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
