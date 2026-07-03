import { useEffect, useRef } from "react";
import { STEP_META, StepChip } from "../Markdown";
import { ApprovalCard } from "../TaskViews";
import TimelineCard from "../TimelineCard";
import { Message, PROVIDER_DOT, ProviderMark } from "../conversation/Message";
import { BeanMark, ChatBubble, Spinner } from "../icons";
import { EmptyState } from "../ui";
import { cardFromStreamEvent } from "../../lib/displayModel";
import { useRecentEvents, useRunStream } from "../../stream";
import type { Approval, ChatMessage, ChatPending, QueueState, RunInfo } from "../../types";
import AgentDockLiveRun from "./AgentDockLiveRun";

/* The dock transcript: completed messages render statically (never
   reanimated); the in-flight reply and active runs stream from the shared
   event store via useRunStream; structural transitions render as compact
   TimelineCards. See docs/cli-interface-mythos-revamp.md Workstream 1. */

function elapsed(startedAt?: string): string {
  if (!startedAt) return "";
  const s = Math.max(0, Math.round((Date.now() - Date.parse(startedAt)) / 1000));
  return s < 90 ? `${s}s` : `${Math.round(s / 60)}m`;
}

const ACTIVE = ["queued", "awaiting_approval", "blocked", "running"];

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
            <AgentDockLiveRun runId={orchestrating.id} />
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
              <AgentDockLiveRun runId={run?.id ?? i.runId} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function AgentDockTranscript({
  hasWorkspace,
  loaded,
  messages,
  isOrch,
  channel,
  selected,
  queue,
  running,
  approvals,
  pending,
  busy,
  onResolveApproval,
}: {
  hasWorkspace: boolean;
  /** chat state has arrived (distinguishes "empty chat" from "still loading"). */
  loaded: boolean;
  messages: ChatMessage[];
  isOrch: boolean;
  channel: string;
  /** the controller's engine pick — labels the in-flight reply. */
  selected: string;
  queue: QueueState | null;
  running: RunInfo[];
  approvals: Approval[];
  pending: ChatPending | null;
  busy: boolean;
  onResolveApproval: (id: string, approve: boolean) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  // Subscribed only to keep the transcript pinned to the bottom while the
  // in-flight reply streams; AgentDockLiveRun renders the text itself.
  const liveReply = useRunStream(pending?.runId);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, liveReply?.stdout, liveReply?.stderr, busy, channel]);

  return (
    <div ref={scrollRef} className="min-h-0 flex-1 space-y-2.5 overflow-y-auto px-3 py-3">
      {!hasWorkspace ? (
        <EmptyState className="h-full" icon={<ChatBubble />} message="Open a workspace to start." />
      ) : loaded && messages.length === 0 && !pending ? (
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
                Direct chat with <span className="font-mono">{channel}</span> — no tasks, no queue.
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
            onApprove={(id) => onResolveApproval(id, true)}
            onReject={(id) => onResolveApproval(id, false)}
          />
        ))}

      {pending && (
        <div className="flex w-full flex-col items-start gap-1">
          <span className="flex items-center gap-1.5 px-1 text-[10px] text-neutral-400">
            <Spinner className="h-3 w-3" />
            <ProviderMark id={isOrch ? selected : channel} className="h-3 w-3" />
            <span className="font-mono">{isOrch ? selected : channel}</span> is working…
          </span>
          {/* The real activity — narration, commands, results — streamed from the
              shared event store; never a cached tail behind a "thinking" label. */}
          <AgentDockLiveRun runId={pending.runId} provider={isOrch ? selected : channel} />
        </div>
      )}
    </div>
  );
}
