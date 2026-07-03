import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import type { PageId } from "../ActivityBar";
import type { ChatMessage, ChatSendResult, CurrentProject, GitInfo, Usage } from "../../types";
import CommandPalette, { type PaletteAction } from "../CommandPalette";
import DragHandle from "../DragHandle";
import TerminalPane from "../TerminalPane";
import { ProviderMark } from "../conversation/Message";
import { BeanMark } from "../icons";
import { useDockData } from "../../hooks/useDockData";
import { loadState, saveState } from "../../persist";
import AgentDockComposer from "./AgentDockComposer";
import AgentDockFooter from "./AgentDockFooter";
import AgentDockTabs, { type DockTab } from "./AgentDockTabs";
import AgentDockTerminalDrawer from "./AgentDockTerminalDrawer";
import AgentDockTranscript from "./AgentDockTranscript";

/* The right-hand Agent Dock — the live command center for the controller and a
   direct line to each agent CLI. This file owns only the frame: resize,
   collapsed rail, tab/channel state, palette, and composition of the dock
   subcomponents (Tabs / Transcript / TerminalDrawer / Composer / Footer).
   Data fetching lives in useDockData; live text lives in the stream store. */

const OPEN_KEY = "agentflow.chatOpen";
const ORCH = "orchestrator";
const FALLBACK_AGENTS = ["codex", "claude", "antigravity"];
const TERM_MIN_W = 600; // ≈80 mono columns — the classic terminal minimum
const MAX_W = 900;

export default function AgentDock({
  workspacePath,
  project = null,
  git = null,
  usage = null,
  onNavigate,
}: {
  workspacePath: string | null;
  project?: CurrentProject | null;
  git?: GitInfo | null;
  usage?: Usage | null;
  onNavigate?: (page: PageId) => void;
}) {
  const hasWorkspace = Boolean(workspacePath);
  const [open, setOpen] = useState(() => localStorage.getItem(OPEN_KEY) !== "0");
  const [width, setWidth] = useState(() => loadState("chatW", 384));
  const widthRef = useRef(width);
  // Data/fetching/polling live in the hook; the dock composes rendering.
  const { data, queue, running, approvals, busy, reload } = useDockData(workspacePath, open);
  const [provider, setProvider] = useState<string | null>(null);
  const [channel, setChannel] = useState<string>(() => loadState("chatTab", ORCH));
  const [seen, setSeen] = useState<Record<string, number>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [termOpen, setTermOpen] = useState(false);

  const isOrch = channel === ORCH;

  const toggle = (next: boolean) => {
    setOpen(next);
    localStorage.setItem(OPEN_KEY, next ? "1" : "0");
  };

  const switchTab = (id: string) => {
    setChannel(id);
    saveState("chatTab", id);
    setNotice(null);
  };

  // Reset local UI state on workspace change (data/queue/etc. reset in the hook).
  useEffect(() => {
    setNotice(null);
    setProvider(null);
    setSeen({});
  }, [workspacePath]);

  const resolveApproval = useCallback(
    async (id: string, approve: boolean) => {
      try {
        await (approve ? api.approvalApprove(id) : api.approvalReject(id));
      } catch (e) {
        setNotice(e instanceof Error ? e.message : String(e));
      }
      await reload();
    },
    [reload],
  );

  const channelMessages = (id: string): ChatMessage[] =>
    id === ORCH ? (data?.messages ?? []) : (data?.channels?.[id] ?? []);
  const messages = channelMessages(channel);
  const pending = (isOrch ? data?.pending : data?.channelPending?.[channel]) ?? null;

  // The active tab is always caught up; other tabs flag replies that arrived meanwhile.
  useEffect(() => {
    if (!data) return;
    setSeen((prev) => {
      const next = { ...prev };
      for (const id of [ORCH, ...Object.keys(data.channels ?? {})]) {
        const len = id === ORCH ? data.messages.length : (data.channels?.[id] ?? []).length;
        if (next[id] === undefined || id === channel) next[id] = len;
      }
      return next;
    });
  }, [data, channel]);

  const hasUnread = (id: string) => {
    const len = channelMessages(id).length;
    return len > (seen[id] ?? len);
  };

  // After a typed submission resolves: surface non-success status, then refresh so
  // the user message + pending reply (which streams via the event store) appear.
  const onSubmitResult = (res: ChatSendResult) => {
    setNotice(
      ["error", "busy", "provider_missing", "claude_red"].includes(res.status)
        ? (res.message ?? res.status)
        : null,
    );
    void reload();
  };

  // ⌘K / Ctrl+K opens the native action palette.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const channelIds = [ORCH, ...(data?.providers?.map((p) => p.id) ?? FALLBACK_AGENTS)];
  const paletteActions = useMemo<PaletteAction[]>(() => {
    const acts: PaletteAction[] = [];
    if (onNavigate) {
      acts.push({
        id: "nav-tasks",
        label: "Open Tasks",
        hint: "history",
        run: () => onNavigate("tasks"),
      });
      acts.push({
        id: "nav-usage",
        label: "Open Usage — traffic control",
        run: () => onNavigate("usage"),
      });
    }
    for (const a of approvals) {
      acts.push({
        id: `appr-${a.id}`,
        label: `Approve: ${a.action}`,
        hint: a.provider ?? "approval",
        run: () => void resolveApproval(a.id, true),
      });
      acts.push({
        id: `rej-${a.id}`,
        label: `Reject: ${a.action}`,
        hint: a.provider ?? "approval",
        run: () => void resolveApproval(a.id, false),
      });
    }
    if (pending && isOrch)
      acts.push({
        id: "stop-resp",
        label: "Stop response",
        hint: channel,
        run: () => void api.chatStop(channel).then(reload),
      });
    if (running.length > 0)
      acts.push({
        id: "stop-all",
        label: "Stop all running processes",
        run: () => void api.stop().then(reload),
      });
    if (isOrch)
      acts.push({
        id: "clear",
        label: "Clear this chat",
        hint: "controller",
        run: () => void api.chatClear(channel).then(reload),
      });
    for (const id of channelIds) {
      if (id !== channel)
        acts.push({
          id: `chan-${id}`,
          label: `Switch to ${id === ORCH ? "controller" : id}`,
          hint: id === ORCH ? "controller" : id,
          run: () => switchTab(id),
        });
    }
    return acts;
  }, [
    onNavigate,
    approvals,
    pending,
    running.length,
    channel,
    isOrch,
    channelIds.join(","),
    resolveApproval,
    reload,
  ]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) {
    // Collapsed rail: one icon per channel — opens the dock straight onto that conversation.
    const agents = data?.providers?.map((p) => p.id) ?? FALLBACK_AGENTS;
    return (
      <div className="flex w-10 shrink-0 flex-col items-center gap-1 border-l border-neutral-200 bg-white py-2 dark:border-neutral-800 dark:bg-neutral-900">
        <button
          onClick={() => {
            switchTab(ORCH);
            toggle(true);
          }}
          title="Controller"
          aria-label="Open controller chat"
          className="focusable relative cursor-pointer rounded-lg p-2 text-neutral-500 transition-colors duration-150 hover:bg-neutral-100 hover:text-neutral-800 dark:hover:bg-neutral-800 dark:hover:text-neutral-200"
        >
          <BeanMark className="h-[18px] w-[18px]" />
          {(hasUnread(ORCH) || data?.pending) && (
            <span
              className={`absolute right-0 top-0 h-1.5 w-1.5 rounded-full border border-white bg-accent dark:border-neutral-900 ${data?.pending ? "animate-pulse" : ""}`}
              aria-hidden="true"
            />
          )}
        </button>
        {agents.map((id) => {
          const chPending = data?.channelPending?.[id];
          return (
            <button
              key={id}
              onClick={() => {
                switchTab(id);
                toggle(true);
              }}
              title={`${id} terminal`}
              aria-label={`Open ${id} terminal`}
              className="focusable relative flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg transition-colors duration-150 hover:bg-neutral-100 dark:hover:bg-neutral-800"
            >
              <span className={chPending ? "animate-pulse" : ""}>
                <ProviderMark id={id} className="h-[18px] w-[18px]" />
              </span>
              {hasUnread(id) && (
                <span
                  className="absolute right-0 top-0 h-1.5 w-1.5 rounded-full border border-white bg-accent dark:border-neutral-900"
                  aria-hidden="true"
                />
              )}
            </button>
          );
        })}
      </div>
    );
  }

  const fallback =
    data?.providers.find((p) => p.id === data.defaultProvider && p.installed)?.id ??
    data?.providers.find((p) => p.installed)?.id ??
    data?.defaultProvider ??
    "claude";
  const selected = provider ?? fallback;

  const tabs: DockTab[] = channelIds.map((id) => ({
    id,
    controller: id === ORCH,
    installed: id === ORCH || (data?.providers?.find((p) => p.id === id)?.installed ?? true),
    pending: Boolean(id === ORCH ? data?.pending : data?.channelPending?.[id]),
    unread: hasUnread(id),
  }));

  // A PTY needs ~80 mono columns (≈600px at the pane's 12px font) or TUIs like
  // agy reflow into garbage. The whole dock — controller tab included — keeps
  // that same minimum so the toolbar doesn't jump between tabs. Guarded so it
  // never overflows a small window.
  const minWidth = Math.min(TERM_MIN_W, Math.max(300, window.innerWidth - 240));
  const shownWidth = Math.max(width, minWidth);

  return (
    <div className="flex shrink-0">
      <DragHandle
        orientation="vertical"
        label="Resize controller panel"
        onMove={(x) => {
          const w = Math.min(MAX_W, Math.max(minWidth, window.innerWidth - x));
          widthRef.current = w;
          setWidth(w);
        }}
        onDone={() => saveState("chatW", widthRef.current)}
      />
      <section
        style={{ width: shownWidth }}
        className="flex shrink-0 flex-col border-l border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900"
        aria-label="Agent chat"
      >
        <AgentDockTabs
          tabs={tabs}
          channel={channel}
          termOpen={termOpen}
          showTerminalToggle={isOrch}
          showClear={isOrch}
          onSwitch={switchTab}
          onOpenPalette={() => setPaletteOpen(true)}
          onToggleTerminal={() => setTermOpen((v) => !v)}
          onClear={() => {
            if (window.confirm("Clear the controller chat for this workspace?")) {
              void api.chatClear(channel).then(reload);
            }
          }}
          onCollapse={() => toggle(false)}
        />

        {isOrch ? (
          <>
            <AgentDockTranscript
              hasWorkspace={hasWorkspace}
              loaded={data !== null}
              messages={messages}
              isOrch={isOrch}
              channel={channel}
              selected={selected}
              queue={queue}
              running={running}
              approvals={approvals}
              pending={pending}
              busy={busy}
              onResolveApproval={(id, approve) => void resolveApproval(id, approve)}
            />

            {/* engine terminal drawer — the controller CLI's PTY, on demand */}
            {termOpen && hasWorkspace && <AgentDockTerminalDrawer provider={selected} />}

            <AgentDockComposer
              workspacePath={workspacePath}
              isOrch={isOrch}
              channel={channel}
              selected={selected}
              providers={data?.providers}
              usage={usage}
              pending={!!pending}
              notice={notice}
              onProviderChange={setProvider}
              onResult={onSubmitResult}
              onStop={() => void api.chatStop(channel).then(reload)}
            />
          </>
        ) : hasWorkspace ? (
          // Agent tabs ARE the terminals: one live PTY per agent, right here —
          // no separate Terminals page showing the same sessions in another style.
          <TerminalPane key={channel} provider={channel} compact />
        ) : (
          <div className="flex min-h-0 flex-1 items-center justify-center text-xs text-neutral-400">
            Open a workspace to start.
          </div>
        )}

        <AgentDockFooter
          project={project}
          git={git}
          workspacePath={workspacePath}
          selected={selected}
          queue={queue}
          runningCount={running.length}
          usage={usage}
        />
      </section>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        actions={paletteActions}
      />
    </div>
  );
}
