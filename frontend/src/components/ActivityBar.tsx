import { TopHat } from "./icons";

export type PageId = "projects" | "agents" | "tasks" | "preview" | "usage" | "logs" | "settings";

interface NavItem {
  id: PageId;
  label: string;
  icon: JSX.Element;
}

const MAIN_NAV: NavItem[] = [
  {
    id: "projects",
    label: "Explorer",
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
  { id: "tasks", label: "Tasks", icon: <path d="M5 7h10M5 12h14M5 17h8M19 5l-2 2" /> },
  {
    id: "preview",
    label: "Preview",
    icon: (
      <>
        <rect x="3" y="5" width="18" height="13" rx="2" />
        <path d="M9 21h6M10 9.5l4 2-4 2v-4z" />
      </>
    ),
  },
  { id: "usage", label: "Usage", icon: <path d="M5 19V11M10 19V5M15 19v-6M20 19V9" /> },
  { id: "logs", label: "Logs", icon: <path d="M5 6l4 4-4 4M11 16h8" /> },
];

const SETTINGS_NAV: NavItem = {
  id: "settings",
  label: "Settings",
  icon: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3 1a7 7 0 0 0-2.1-1.3L14 3h-4l-.5 2.6a7 7 0 0 0-2.1 1.3l-2.3-1-2 3.4 2 1.5A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.4 2.3-1a7 7 0 0 0 2.1 1.3L10 21h4l.5-2.6a7 7 0 0 0 2.1-1.3l2.3 1 2-3.4-2-1.5c.1-.4.1-.8.1-1.2z" />
    </>
  ),
};

function RailButton({ item, active, onClick }: { item: NavItem; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      title={item.label}
      aria-label={item.label}
      aria-current={active ? "page" : undefined}
      className={`focusable relative flex h-10 w-10 cursor-pointer items-center justify-center rounded-lg transition-colors duration-150 ${
        active
          ? "bg-accent/10 text-blue-700 dark:bg-accent/20 dark:text-blue-300"
          : "text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800 dark:text-neutral-400 dark:hover:bg-neutral-800 dark:hover:text-neutral-200"
      }`}
    >
      {active && (
        <span
          className="absolute -left-1.5 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-accent"
          aria-hidden="true"
        />
      )}
      <svg
        viewBox="0 0 24 24"
        className="h-5 w-5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        {item.icon}
      </svg>
    </button>
  );
}

interface Props {
  page: PageId;
  onNavigate: (page: PageId) => void;
}

/** VS Code-style activity bar: icon rail with the Settings gear pinned at the bottom. */
export default function ActivityBar({ page, onNavigate }: Props) {
  return (
    <aside
      className="flex w-12 shrink-0 flex-col items-center gap-1 border-r border-neutral-200 bg-white py-2 dark:border-neutral-800 dark:bg-neutral-900"
      aria-label="Main navigation"
    >
      <div
        className="mb-2 flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-sm"
        title="AgentFlow Studio (beta)"
      >
        <TopHat className="h-5 w-5" />
      </div>
      {MAIN_NAV.map((item) => (
        <RailButton key={item.id} item={item} active={page === item.id} onClick={() => onNavigate(item.id)} />
      ))}
      <div className="mt-auto">
        <RailButton item={SETTINGS_NAV} active={page === "settings"} onClick={() => onNavigate("settings")} />
      </div>
    </aside>
  );
}
