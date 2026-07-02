import { ProviderMark } from "../conversation/Message";
import { BeanMark, ChevronRight, Close, Command, Terminal } from "../icons";

/** One dock tab's display state, prepared by AgentDock. */
export interface DockTab {
  id: string;
  /** true for the controller tab (bean mark + medium label). */
  controller: boolean;
  installed: boolean;
  /** a reply is in flight on this channel. */
  pending: boolean;
  unread: boolean;
}

/** The dock tab strip: controller + a direct line to each agent, with
 *  unread/running state, plus the right-side dock controls (palette, terminal
 *  drawer, clear, collapse). Pure presentation — AgentDock owns the state. */
export default function AgentDockTabs({
  tabs,
  channel,
  termOpen,
  onSwitch,
  onOpenPalette,
  onToggleTerminal,
  onClear,
  onCollapse,
}: {
  tabs: DockTab[];
  channel: string;
  termOpen: boolean;
  onSwitch: (id: string) => void;
  onOpenPalette: () => void;
  onToggleTerminal: () => void;
  onClear: () => void;
  onCollapse: () => void;
}) {
  return (
    <div className="flex h-8 shrink-0 items-stretch border-b border-neutral-200 bg-surface dark:border-neutral-800 dark:bg-neutral-950">
      <div
        role="tablist"
        aria-label="Chat channel"
        className="flex min-w-0 flex-1 items-stretch overflow-x-auto"
      >
        {tabs.map((tab) => {
          const active = tab.id === channel;
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={active}
              onClick={() => onSwitch(tab.id)}
              title={
                !tab.installed
                  ? `${tab.id} is not installed`
                  : tab.controller
                    ? "Controller — creates tasks and cues the agents"
                    : `Direct chat with ${tab.id} — no traffic control`
              }
              className={`focusable relative flex shrink-0 cursor-pointer items-center gap-1.5 border-r border-neutral-200 px-2.5 text-[11px] transition-colors duration-150 dark:border-neutral-800 ${
                active
                  ? "bg-white text-neutral-800 dark:bg-neutral-900 dark:text-neutral-100"
                  : "text-neutral-500 hover:bg-neutral-100 hover:text-neutral-700 dark:text-neutral-400 dark:hover:bg-neutral-800/60 dark:hover:text-neutral-200"
              }`}
            >
              {active && (
                <span className="absolute inset-x-0 top-0 h-0.5 bg-accent" aria-hidden="true" />
              )}
              {tab.controller ? (
                <BeanMark className="h-4 w-4 text-accent-subtle" />
              ) : (
                <span
                  className={`${tab.pending ? "animate-pulse" : ""} ${tab.installed ? "" : "opacity-40"}`}
                >
                  <ProviderMark id={tab.id} className="h-4 w-4" />
                </span>
              )}
              {/* The active channel announces itself; the rest are just their marks. */}
              {active && (
                <span className={tab.controller ? "font-medium" : "font-mono"}>
                  {tab.controller ? "controller" : tab.id}
                </span>
              )}
              {!active && tab.unread && (
                <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
              )}
            </button>
          );
        })}
      </div>
      <div className="flex shrink-0 items-center gap-0.5 px-1">
        <button
          onClick={onOpenPalette}
          title="Command palette (⌘K)"
          aria-label="Open command palette"
          className="icon-btn"
        >
          <Command className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onToggleTerminal}
          title={termOpen ? "Close terminal drawer" : "Open terminal drawer"}
          aria-label={termOpen ? "Close terminal drawer" : "Open terminal drawer"}
          aria-pressed={termOpen}
          className={`icon-btn ${termOpen ? "text-accent" : ""}`}
        >
          <Terminal className="h-3.5 w-3.5" />
        </button>
        <button onClick={onClear} title="Clear this chat" aria-label="Clear this chat" className="icon-btn">
          <Close className="h-3.5 w-3.5" />
        </button>
        <button onClick={onCollapse} title="Collapse chat" aria-label="Collapse chat" className="icon-btn">
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
