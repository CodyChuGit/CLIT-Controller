import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { PageId } from "./ActivityBar";
import type {
  ChatMessage,
  ChatSendResult,
  CurrentProject,
  GitInfo,
  QueueState,
  RunInfo,
  Usage,
} from "../types";
import DragHandle from "./DragHandle";
import { STEP_META, StepChip } from "./Markdown";
import { ApprovalCard, LiveOutput } from "./TaskViews";
import CommandPalette, { type PaletteAction } from "./CommandPalette";
import SmoothStreamingText from "./SmoothStreamingText";
import { ComposerChip } from "./Composer";
import InputComposer from "./input/InputComposer";
import { Message, PROVIDER_DOT, ProviderMark } from "./conversation/Message";
import TerminalPane from "./TerminalPane";
import TimelineCard from "./TimelineCard";
import { EmptyState } from "./ui";
import { useRecentEvents, useRunStream } from "../stream";
import { cardFromStreamEvent } from "../lib/displayModel";
import { stripResultSentinel } from "../lib/narrative";
import { useDockData } from "../hooks/useDockData";
import { loadState, saveState } from "../persist";
import {
  BeanMark,
  ChatBubble,
  ChevronDown,
  ChevronRight,
  Close,
  Command,
  Folder,
  GitBranch,
  Spinner,
  Terminal,
} from "./icons";

const MODE_LABELS: Record<string, string> = {
  maximum_quality: "Max Quality",
  balanced: "Balanced",
  budget_saver: "Budget Saver",
  manual_approval: "Manual Approval",
};

const HEALTH_DOT: Record<string, string> = {
  green: "bg-emerald-500",
  yellow: "bg-amber-500",
  red: "bg-rose-500",
};

const OPEN_KEY = "agentflow.chatOpen";

/* Conversation message primitives (ProviderMark, SystemNotice, Message) are the
   shared, canonical renderer in ./conversation/Message — Pillar 4. */

/* ----------------------------------------------------- live agent activity */

function elapsed(startedAt?: string): string {
  if (!startedAt) return "";
  const s = Math.max(0, Math.round((Date.now() - Date.parse(startedAt)) / 1000));
  return s < 90 ? `${s}s` : `${Math.round(s / 60)}m`;
}

const ACTIVE = ["queued", "awaiting_approval", "blocked", "running"];

/** Live output for one run, read from the shared event store only — never from
 *  polled log snapshots (revamp Workstream 1 data rule). */
function LiveRunStream({ runId }: { runId: string | null | undefined }) {
  const stream = useRunStream(runId);
  const text = stripResultSentinel(stream?.stdout ?? "");
  if (!text) return null;
  return <LiveOutput text={text} active={stream?.status === "running"} />;
}

/** The most recent structural stream events (queue/task/approval/command/run
 *  transitions) as compact cards — the dock's "what just happened" strip. */
function DockEventCards() {
  const events = useRecentEvents();
  const cards = events
    .slice(-40)
    .map(cardFromStreamEvent)
    .filter((c): c is NonNullable<typeof c> => c !== null)
    .slice(-6);
  if (cards.length === 0) return null;
  return (
    <div className="space-y-1 rounded-md border border-neutral-200 bg-surface px-2.5 py-2 dark:border-neutral-800 dark:bg-neutral-950/60">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-neutral-400">
        Activity
      </div>
      {cards.map((c) => (
        <TimelineCard key={c.id} card={c} density="compact" />
      ))}
    </div>
  );
}

function AgentActivity({ queue, running }: { queue: QueueState | null; running: RunInfo[] }) {
  const items = (queue?.items ?? []).filter((i) => ACTIVE.includes(i.status));
  const orchestrating = running.find((r) => r.step === "orchestrate");
  if (items.length === 0 && !orchestrating) return null;
  return (
    <div className="rounded-md border border-blue-200 bg-gradient-to-br from-blue-50/80 to-violet-50/60 px-2.5 py-2 dark:border-blue-900 dark:from-blue-950/40 dark:to-violet-950/30">
      <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-blue-700 dark:text-blue-300">
        Agents at work
      </div>
      <div className="space-y-1.5">
        {orchestrating && (
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 text-[11px] text-neutral-700 dark:text-neutral-300">
              <Spinner className="h-3 w-3 text-violet-500" />
              <span
                className={`h-2 w-2 rounded-full ${PROVIDER_DOT[orchestrating.provider ?? ""] ?? "bg-neutral-400"}`}
                aria-hidden="true"
              />
              <span className="font-mono">{orchestrating.provider}</span>
              <span>is deciding the next step… {elapsed(orchestrating.startedAt)}</span>
            </div>
            <LiveRunStream runId={orchestrating.id} />
          </div>
        )}
        {items.map((i) => {
          // Which run belongs to this step comes from the structural snapshot;
          // the live text itself streams from the shared event store.
          const run = running.find(
            (r) => r.status === "running" && r.step === i.step && r.taskId === i.taskId,
          );
          return (
            <div key={i.id} className="space-y-1">
              <div className="flex items-center gap-1.5 text-[11px] text-neutral-700 dark:text-neutral-300">
                {i.status === "running" ? (
                  <Spinner className="h-3 w-3 text-blue-500" />
                ) : (
                  <span
                    className={`h-1.5 w-1.5 shrink-0 rounded-full ${i.status === "queued" ? "bg-neutral-400" : "bg-amber-500"}`}
                    aria-hidden="true"
                  />
                )}
                <StepChip name={i.step} />
                <span className="font-mono text-[10px] text-neutral-400">{i.provider}</span>
                <span className="min-w-0 flex-1 truncate">
                  {i.status === "running" && `working… ${elapsed(i.startedAt)}`}
                  {i.status === "queued" && "waiting"}
                  {(i.status === "blocked" || i.status === "awaiting_approval") && "needs approval"}
                </span>
              </div>
              <LiveRunStream runId={run?.id ?? i.runId} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ----------------------------------------------------------- engine select */

/** Controller engine picker with brand marks — native selects can't render SVGs. */
function EngineSelect({
  value,
  options,
  onChange,
}: {
  value: string;
  options: { id: string; installed: boolean }[];
  onChange: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        onClick={() => setOpen(!open)}
        title="CLI that runs the controller"
        aria-label="Controller CLI"
        aria-haspopup="listbox"
        aria-expanded={open}
        className="focusable flex h-[38px] cursor-pointer items-center gap-1.5 rounded-md border border-neutral-200 bg-white px-2 font-mono text-[10px] text-neutral-600 transition-colors duration-150 hover:border-neutral-300 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300 dark:hover:border-neutral-600"
      >
        <ProviderMark id={value} className="h-4 w-4" />
        <ChevronDown
          className={`h-3 w-3 text-neutral-400 transition-transform duration-150 ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div
          role="listbox"
          aria-label="Controller CLI options"
          className="absolute bottom-full left-0 z-20 mb-1 w-44 overflow-hidden rounded-md border border-neutral-200 bg-white py-1 shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
        >
          {options.map((p) => (
            <button
              key={p.id}
              role="option"
              aria-selected={p.id === value}
              onClick={() => {
                onChange(p.id);
                setOpen(false);
              }}
              className={`focusable flex w-full cursor-pointer items-center gap-2 px-2.5 py-1.5 text-left font-mono text-[11px] transition-colors duration-150 hover:bg-neutral-100 dark:hover:bg-neutral-800 ${
                p.id === value
                  ? "text-neutral-900 dark:text-neutral-100"
                  : "text-neutral-500 dark:text-neutral-400"
              }`}
            >
              <ProviderMark id={p.id} className="h-3.5 w-3.5" />
              <span className="flex-1">{p.id}</span>
              {!p.installed && <span className="text-[10px] text-neutral-400">not installed</span>}
              {p.id === value && (
                <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------- panel */

const ORCH = "orchestrator";
const FALLBACK_AGENTS = ["codex", "claude", "antigravity"];

/** Persistent Agent Dock — the controller plus a direct line to each agent. */
export default function ChatPanel({
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
  // Data/fetching/polling live in the hook; ChatPanel composes rendering.
  const { data, queue, running, approvals, busy, reload } = useDockData(workspacePath, open);
  const [provider, setProvider] = useState<string | null>(null);
  const [channel, setChannel] = useState<string>(() => loadState("chatTab", ORCH));
  const [seen, setSeen] = useState<Record<string, number>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [termOpen, setTermOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

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
  // Progressive text for the in-flight reply, streamed from the shared event bus
  // ONLY (streamStore has its own polling fallback on the same bus) — never from
  // the pending.outputTail snapshot. Hide the deterministic result block so its
  // JSON never flashes mid-stream.
  const liveReply = useRunStream(pending?.runId);
  const liveText = stripResultSentinel(liveReply?.stdout ?? "");

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

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, liveReply?.stdout, busy, channel]);

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
        id: "nav-terminals",
        label: "Open Terminals",
        hint: "PTY",
        run: () => onNavigate("terminals"),
      });
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
    if (pending)
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
    acts.push({
      id: "clear",
      label: "Clear this chat",
      hint: isOrch ? "controller" : channel,
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
    // One icon per channel — opens the dock straight onto that conversation.
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
              title={`Chat with ${id}`}
              aria-label={`Open ${id} chat`}
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
    "antigravity";
  const selected = provider ?? fallback;

  return (
    <div className="flex shrink-0">
      <DragHandle
        orientation="vertical"
        label="Resize controller panel"
        onMove={(x) => {
          const w = Math.min(640, Math.max(300, window.innerWidth - x));
          widthRef.current = w;
          setWidth(w);
        }}
        onDone={() => saveState("chatW", widthRef.current)}
      />
      <section
        style={{ width }}
        className="flex shrink-0 flex-col border-l border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900"
        aria-label="Agent chat"
      >
        {/* tab strip: controller + a direct line to each agent */}
        <div className="flex h-8 shrink-0 items-stretch border-b border-neutral-200 bg-surface dark:border-neutral-800 dark:bg-neutral-950">
          <div
            role="tablist"
            aria-label="Chat channel"
            className="flex min-w-0 flex-1 items-stretch overflow-x-auto"
          >
            {[ORCH, ...(data?.providers?.map((p) => p.id) ?? FALLBACK_AGENTS)].map((id) => {
              const active = id === channel;
              const installed =
                id === ORCH || (data?.providers?.find((p) => p.id === id)?.installed ?? true);
              const chPending = id === ORCH ? data?.pending : data?.channelPending?.[id];
              return (
                <button
                  key={id}
                  role="tab"
                  aria-selected={active}
                  onClick={() => switchTab(id)}
                  title={
                    !installed
                      ? `${id} is not installed`
                      : id === ORCH
                        ? "Controller — creates tasks and cues the agents"
                        : `Direct chat with ${id} — no traffic control`
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
                  {id === ORCH ? (
                    <BeanMark className="h-4 w-4 text-accent-subtle" />
                  ) : (
                    <span
                      className={`${chPending ? "animate-pulse" : ""} ${installed ? "" : "opacity-40"}`}
                    >
                      <ProviderMark id={id} className="h-4 w-4" />
                    </span>
                  )}
                  {/* The active channel announces itself; the rest are just their marks. */}
                  {active && (
                    <span className={id === ORCH ? "font-medium" : "font-mono"}>
                      {id === ORCH ? "controller" : id}
                    </span>
                  )}
                  {!active && hasUnread(id) && (
                    <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
                  )}
                </button>
              );
            })}
          </div>
          <div className="flex shrink-0 items-center gap-0.5 px-1">
            <button
              onClick={() => setPaletteOpen(true)}
              title="Command palette (⌘K)"
              aria-label="Open command palette"
              className="icon-btn"
            >
              <Command className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => setTermOpen((v) => !v)}
              title={termOpen ? "Close terminal drawer" : "Open terminal drawer"}
              aria-label={termOpen ? "Close terminal drawer" : "Open terminal drawer"}
              aria-pressed={termOpen}
              className={`icon-btn ${termOpen ? "text-accent" : ""}`}
            >
              <Terminal className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => {
                const label = isOrch ? "controller" : channel;
                if (window.confirm(`Clear the ${label} chat for this workspace?`)) {
                  void api.chatClear(channel).then(reload);
                }
              }}
              title="Clear this chat"
              aria-label="Clear this chat"
              className="icon-btn"
            >
              <Close className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => toggle(false)}
              title="Collapse chat"
              aria-label="Collapse chat"
              className="icon-btn"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* messages */}
        <div ref={scrollRef} className="min-h-0 flex-1 space-y-2.5 overflow-y-auto px-3 py-3">
          {!hasWorkspace ? (
            <EmptyState
              className="h-full"
              icon={<ChatBubble />}
              message="Open a workspace to start."
            />
          ) : data && messages.length === 0 && !pending ? (
            isOrch ? (
              <EmptyState
                className="h-full px-2"
                icon={<BeanMark />}
                message="Ask the controller for work — it creates tasks and cues the agents."
              >
                <div className="flex flex-wrap justify-center gap-1">
                  {Object.keys(STEP_META).map((s) => (
                    <StepChip key={s} name={s} />
                  ))}
                </div>
              </EmptyState>
            ) : (
              <EmptyState
                className="h-full px-2"
                icon={<ProviderMark id={channel} className="h-6 w-6" />}
                message={
                  <>
                    Direct chat with <span className="font-mono">{channel}</span> — no tasks, no
                    queue.
                  </>
                }
              />
            )
          ) : (
            messages.map((m, i) => <Message key={`${m.time}-${i}`} msg={m} direct={!isOrch} />)
          )}

          {isOrch && <AgentActivity queue={queue} running={running} />}

          {isOrch && <DockEventCards />}

          {isOrch &&
            approvals.map((a) => (
              <ApprovalCard
                key={a.id}
                approval={a}
                onApprove={(id) => void resolveApproval(id, true)}
                onReject={(id) => void resolveApproval(id, false)}
              />
            ))}

          {pending && (
            <div className="flex flex-col items-start">
              <span className="mb-0.5 flex items-center gap-1.5 px-1 text-[10px] text-neutral-400">
                <Spinner className="h-3 w-3" />
                <ProviderMark id={isOrch ? selected : channel} className="h-3 w-3" />
                thinking…
              </span>
              {liveText && (
                <pre className="max-h-36 w-full overflow-auto whitespace-pre-wrap rounded-lg border border-blue-200 bg-blue-50/60 p-2 font-mono text-[10px] leading-relaxed text-neutral-600 dark:border-blue-900 dark:bg-blue-950/30 dark:text-neutral-300">
                  <SmoothStreamingText text={liveText} active mode="mono" maxChars={6000} />
                </pre>
              )}
            </div>
          )}
        </div>

        {/* provider terminal drawer — a real PTY without leaving the dock */}
        {termOpen && hasWorkspace && (
          <div className="flex h-64 shrink-0 flex-col">
            <TerminalPane provider={isOrch ? selected : channel} compact />
          </div>
        )}

        {/* notice + input */}
        <div className="shrink-0 border-t border-neutral-200 p-2.5 dark:border-neutral-800">
          {notice && (
            <p className="mb-2 rounded-lg bg-amber-50 px-2.5 py-1.5 text-[11px] text-amber-800 dark:bg-amber-950/50 dark:text-amber-300">
              {notice}
            </p>
          )}
          <InputComposer
            workspaceId={workspacePath ?? "workspace"}
            destination={isOrch ? { kind: "controller" } : { kind: "provider", provider: channel }}
            context={isOrch ? { provider: selected } : undefined}
            onResult={onSubmitResult}
            onStop={pending ? () => void api.chatStop(channel).then(reload) : undefined}
            busy={!!pending}
            disabled={!hasWorkspace}
            placeholder={
              !hasWorkspace
                ? "Open a workspace first"
                : isOrch
                  ? "Ask the controller…"
                  : `Message ${channel} directly…`
            }
            leading={
              isOrch ? (
                <EngineSelect
                  value={selected}
                  options={data?.providers ?? [{ id: selected, installed: true }]}
                  onChange={setProvider}
                />
              ) : undefined
            }
            contextChips={
              isOrch && usage ? (
                <>
                  <ComposerChip title="Traffic control mode">
                    {MODE_LABELS[usage.orchestrationMode] ?? usage.orchestrationMode}
                  </ComposerChip>
                  {["codex", "claude", "antigravity"].map((id) =>
                    usage.providers[id] ? (
                      <ComposerChip
                        key={id}
                        dot={HEALTH_DOT[usage.providers[id].health] ?? "bg-neutral-400"}
                        mono
                        title={`${id} health`}
                      >
                        {id}
                      </ComposerChip>
                    ) : null,
                  )}
                </>
              ) : undefined
            }
          />
        </div>

        {/* dock status footer — mirrors the global status bar density */}
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
              <span
                className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500"
                aria-hidden="true"
              />
              <span className="tabular-nums">{queue!.activeCount} queued</span>
            </span>
          )}
          {running.length > 0 && (
            <span className="flex items-center gap-1">
              <Spinner className="h-3 w-3 text-blue-500" />
              <span className="tabular-nums">{running.length}</span>
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
      </section>

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        actions={paletteActions}
      />
    </div>
  );
}
