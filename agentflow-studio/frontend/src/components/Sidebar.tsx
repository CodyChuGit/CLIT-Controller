import type { CurrentProject } from "../types";

export type PageId = "projects" | "agents" | "tasks" | "usage" | "logs" | "settings";

const NAV: { id: PageId; label: string; icon: JSX.Element }[] = [
  {
    id: "projects",
    label: "Projects",
    icon: (
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
    ),
  },
  {
    id: "agents",
    label: "Agents",
    icon: (
      <>
        <rect x="5" y="7" width="14" height="11" rx="2" />
        <path d="M12 7V4M8 11h.01M16 11h.01M9 15h6" />
      </>
    ),
  },
  {
    id: "tasks",
    label: "Tasks",
    icon: <path d="M5 7h10M5 12h14M5 17h8M19 5l-2 2" />,
  },
  {
    id: "usage",
    label: "Usage",
    icon: <path d="M5 19V11M10 19V5M15 19v-6M20 19V9" />,
  },
  {
    id: "logs",
    label: "Logs",
    icon: <path d="M5 6l4 4-4 4M11 16h8" />,
  },
  {
    id: "settings",
    label: "Settings",
    icon: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3 1a7 7 0 0 0-2.1-1.3L14 3h-4l-.5 2.6a7 7 0 0 0-2.1 1.3l-2.3-1-2 3.4 2 1.5A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.4 2.3-1a7 7 0 0 0 2.1 1.3L10 21h4l.5-2.6a7 7 0 0 0 2.1-1.3l2.3 1 2-3.4-2-1.5c.1-.4.1-.8.1-1.2z" />
      </>
    ),
  },
];

interface Props {
  page: PageId;
  onNavigate: (page: PageId) => void;
  project: CurrentProject | null;
  backendUp: boolean;
}

export default function Sidebar({ page, onNavigate, project, backendUp }: Props) {
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-neutral-200 bg-white/70 backdrop-blur dark:border-neutral-800 dark:bg-neutral-900/70">
      <div className="flex items-center gap-2.5 px-5 pb-4 pt-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 text-sm font-bold text-white shadow-sm">
          A
        </div>
        <div>
          <div className="text-sm font-semibold leading-tight">AgentFlow Studio</div>
          <div className="text-[11px] text-neutral-400">local beta</div>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 px-3">
        {NAV.map((item) => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
              page === item.id
                ? "bg-blue-600/10 font-medium text-blue-700 dark:bg-blue-500/15 dark:text-blue-300"
                : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800"
            }`}
          >
            <svg
              viewBox="0 0 24 24"
              className="h-4 w-4 shrink-0"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {item.icon}
            </svg>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="border-t border-neutral-200 px-5 py-4 text-xs dark:border-neutral-800">
        <div className="mb-1 flex items-center gap-1.5">
          <span className={`h-2 w-2 rounded-full ${backendUp ? "bg-emerald-500" : "bg-rose-500"}`} />
          <span className="text-neutral-500">{backendUp ? "Backend :8787" : "Backend offline"}</span>
        </div>
        <div className="truncate font-medium text-neutral-700 dark:text-neutral-300" title={project?.workspacePath ?? ""}>
          {project?.workspacePath ? project.name : "No workspace"}
        </div>
      </div>
    </aside>
  );
}
