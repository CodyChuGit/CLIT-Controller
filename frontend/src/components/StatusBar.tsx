import type { PageId } from "./ActivityBar";
import { Folder, GitBranch } from "./icons";
import { useConnection } from "../stream";
import type { CurrentProject, GitInfo, Usage } from "../types";

const MODE_LABELS: Record<string, string> = {
  maximum_quality: "Maximum Quality",
  balanced: "Balanced",
  budget_saver: "Budget Saver",
  manual_approval: "Manual Approval",
};

interface Props {
  backendUp: boolean;
  project: CurrentProject | null;
  git: GitInfo | null;
  usage: Usage | null;
  queuedCount: number;
  onNavigate: (page: PageId) => void;
}

function Item({
  onClick,
  title,
  children,
}: {
  onClick?: () => void;
  title?: string;
  children: React.ReactNode;
}) {
  if (!onClick) {
    return <span className="flex items-center gap-1 px-1.5">{children}</span>;
  }
  return (
    <button
      onClick={onClick}
      title={title}
      className="focusable flex cursor-pointer items-center gap-1 rounded-sm px-1.5 py-0.5 transition-colors duration-150 hover:bg-neutral-100 dark:hover:bg-neutral-800"
    >
      {children}
    </button>
  );
}

/** Quiet status strip: neutral surface, color only as signal. */
export default function StatusBar({
  backendUp,
  project,
  git,
  usage,
  queuedCount,
  onNavigate,
}: Props) {
  const changed = git?.changedFileCount ?? 0;
  const connection = useConnection();
  return (
    <footer
      className="flex h-6 shrink-0 items-center gap-0.5 border-t border-neutral-200 bg-white px-1.5 text-[11px] text-neutral-600 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-400"
      aria-label="Status bar"
    >
      <Item>
        <span
          className={`h-2 w-2 rounded-full ${backendUp ? "bg-emerald-500" : "bg-rose-500"}`}
          aria-hidden="true"
        />
        <span className={backendUp ? "" : "font-medium text-rose-600 dark:text-rose-400"}>
          {backendUp ? "Backend :8787" : "Backend offline"}
        </span>
      </Item>

      {project?.workspacePath && (
        <Item onClick={() => onNavigate("projects")} title={project.workspacePath}>
          <Folder className="h-3 w-3" />
          {project.name}
        </Item>
      )}

      {git?.isRepo && (
        <Item onClick={() => onNavigate("projects")} title="Git branch (open Explorer)">
          <GitBranch className="h-3 w-3" />
          {git.branch}
          {changed > 0 && (
            <span className="tabular-nums text-amber-600 dark:text-amber-400">±{changed}</span>
          )}
        </Item>
      )}

      {queuedCount > 0 && (
        <Item onClick={() => onNavigate("tasks")} title="Execution queue (open Tasks)">
          <span className="h-2 w-2 animate-pulse rounded-full bg-blue-500" aria-hidden="true" />
          <span className="tabular-nums">{queuedCount} queued</span>
        </Item>
      )}

      <span className="flex-1" />

      {usage && (
        <Item onClick={() => onNavigate("usage")} title="Traffic control mode (open Usage)">
          {MODE_LABELS[usage.orchestrationMode] ?? usage.orchestrationMode}
        </Item>
      )}
      {project?.workspacePath && connection !== "live" && (
        <Item
          title={
            connection === "polling"
              ? "Streaming degraded — polling for updates"
              : "Streaming offline"
          }
        >
          <span
            className={`h-2 w-2 rounded-full ${connection === "polling" ? "bg-amber-500" : "bg-neutral-400"}`}
            aria-hidden="true"
          />
          {connection === "polling" ? "polling" : "stream off"}
        </Item>
      )}
      <Item>CLIT Controller IDE 0.1 beta</Item>
    </footer>
  );
}
