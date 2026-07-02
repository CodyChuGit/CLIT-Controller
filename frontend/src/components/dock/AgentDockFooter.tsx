import { ProviderMark } from "../conversation/Message";
import { Folder, GitBranch, Spinner } from "../icons";
import { useConnection } from "../../stream";
import type { CurrentProject, GitInfo, QueueState, Usage } from "../../types";

export const MODE_LABELS: Record<string, string> = {
  maximum_quality: "Max Quality",
  balanced: "Balanced",
  budget_saver: "Budget Saver",
  manual_approval: "Manual Approval",
};

export const HEALTH_DOT: Record<string, string> = {
  green: "bg-emerald-500",
  yellow: "bg-amber-500",
  red: "bg-rose-500",
};

/** Dock status footer — workspace, branch, controller engine, queue/run counts,
 *  provider health, traffic-control mode, and (quietly) stream health when the
 *  live event stream has degraded to polling. Mirrors the global status bar
 *  density. */
export default function AgentDockFooter({
  project,
  git,
  workspacePath,
  selected,
  queue,
  runningCount,
  usage,
}: {
  project: CurrentProject | null;
  git: GitInfo | null;
  workspacePath: string | null;
  selected: string;
  queue: QueueState | null;
  runningCount: number;
  usage: Usage | null;
}) {
  const connection = useConnection();
  return (
    <div className="flex h-6 shrink-0 items-center gap-2 overflow-hidden border-t border-neutral-200 bg-surface px-2 text-[10px] text-neutral-500 dark:border-neutral-800 dark:bg-neutral-950">
      {project?.name && (
        <span
          className="flex max-w-[38%] items-center gap-1 truncate font-mono"
          title={workspacePath ?? undefined}
        >
          <Folder className="h-3 w-3 shrink-0" />
          {project.name}
        </span>
      )}
      {git?.isRepo && (
        <span className="flex items-center gap-1 font-mono">
          <GitBranch className="h-3 w-3 shrink-0" />
          {git.branch}
          {(git.changedFileCount ?? 0) > 0 && (
            <span className="tabular-nums text-amber-600 dark:text-amber-400">
              ±{git.changedFileCount}
            </span>
          )}
        </span>
      )}
      <span className="flex items-center gap-1">
        <ProviderMark id={selected} className="h-3 w-3" />
        <span className="font-mono">{selected}</span>
      </span>
      {(queue?.activeCount ?? 0) > 0 && (
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" aria-hidden="true" />
          <span className="tabular-nums">{queue!.activeCount} queued</span>
        </span>
      )}
      {runningCount > 0 && (
        <span className="flex items-center gap-1">
          <Spinner className="h-3 w-3 text-blue-500" />
          <span className="tabular-nums">{runningCount}</span>
        </span>
      )}
      {connection === "polling" && (
        <span
          className="flex items-center gap-1 text-amber-600 dark:text-amber-400"
          title="Live event stream degraded — using the polling fallback"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-amber-500" aria-hidden="true" />
          polling
        </span>
      )}
      <span className="flex-1" />
      {usage &&
        ["codex", "claude", "antigravity"].map((id) =>
          usage.providers[id] ? (
            <span
              key={id}
              className={`h-1.5 w-1.5 rounded-full ${HEALTH_DOT[usage.providers[id].health] ?? "bg-neutral-400"}`}
              title={`${id}: ${usage.providers[id].health}`}
              aria-hidden="true"
            />
          ) : null,
        )}
      {usage && (
        <span className="font-mono">
          {MODE_LABELS[usage.orchestrationMode] ?? usage.orchestrationMode}
        </span>
      )}
    </div>
  );
}
