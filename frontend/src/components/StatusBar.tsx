import type { PageId } from "./ActivityBar";
import { Folder, GitBranch } from "./icons";
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
      className="focusable flex cursor-pointer items-center gap-1 rounded-sm px-1.5 py-0.5 transition-colors duration-150 hover:bg-white/20"
    >
      {children}
    </button>
  );
}

/** VS Code-style status bar: the iconic accent strip across the bottom. */
export default function StatusBar({ backendUp, project, git, usage, queuedCount, onNavigate }: Props) {
  const changed = git?.changedFileCount ?? 0;
  return (
    <footer
      className={`flex h-6 shrink-0 items-center gap-0.5 px-1.5 text-[11px] text-white/90 ${
        backendUp ? "bg-accent" : "bg-rose-600"
      }`}
      aria-label="Status bar"
    >
      <Item>
        <span className={`h-2 w-2 rounded-full ${backendUp ? "bg-emerald-300" : "bg-white"}`} aria-hidden="true" />
        {backendUp ? "Backend :8787" : "Backend offline"}
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
          {changed > 0 && <span className="tabular-nums text-amber-200">±{changed}</span>}
        </Item>
      )}

      {queuedCount > 0 && (
        <Item onClick={() => onNavigate("tasks")} title="Execution queue (open Tasks)">
          <span className="h-2 w-2 animate-pulse rounded-full bg-white" aria-hidden="true" />
          <span className="tabular-nums">{queuedCount} queued</span>
        </Item>
      )}

      <span className="flex-1" />

      {usage && (
        <Item onClick={() => onNavigate("usage")} title="Orchestration mode (open Usage)">
          {MODE_LABELS[usage.orchestrationMode] ?? usage.orchestrationMode}
        </Item>
      )}
      <Item>AgentFlow 0.1 beta</Item>
    </footer>
  );
}
