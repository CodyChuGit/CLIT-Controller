import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ChatMessage, ChatState, QueueState, RunInfo } from "../types";
import { ChatBubble, ChevronRight, Close, Send, Spinner, StopSquare } from "./icons";

const OPEN_KEY = "agentflow.chatOpen";
const COLLAPSE_CHARS = 600; // longer messages start collapsed ("Show more")

/* ------------------------------------------------- message rendering helpers */

type Segment = { kind: "text"; text: string } | { kind: "code"; lang: string; code: string };

function parseSegments(content: string): Segment[] {
  const segments: Segment[] = [];
  const re = /```([\w-]*)\s*\n([\s\S]*?)```/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(content)) !== null) {
    if (m.index > last) segments.push({ kind: "text", text: content.slice(last, m.index) });
    segments.push({ kind: "code", lang: m[1] ?? "", code: m[2] ?? "" });
    last = re.lastIndex;
  }
  if (last < content.length) segments.push({ kind: "text", text: content.slice(last) });
  return segments;
}

/** Minimal inline markdown: **bold** and `code`. */
function renderInline(text: string): React.ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code key={i} className="rounded bg-neutral-100 px-1 font-mono text-[10px] dark:bg-neutral-700/60">
          {part.slice(1, -1)}
        </code>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

function TextBlock({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-0.5">
      {lines.map((line, i) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={i} className="h-1.5" />;
        if (/^#{1,4}\s/.test(trimmed)) {
          return (
            <div key={i} className="pt-1 text-xs font-semibold">
              {renderInline(trimmed.replace(/^#{1,4}\s/, ""))}
            </div>
          );
        }
        if (/^[-*]\s+/.test(trimmed)) {
          return (
            <div key={i} className="flex gap-1.5 pl-1">
              <span className="text-neutral-400">•</span>
              <span className="min-w-0 flex-1">{renderInline(trimmed.replace(/^[-*]\s+/, ""))}</span>
            </div>
          );
        }
        return <div key={i}>{renderInline(line)}</div>;
      })}
    </div>
  );
}

const DIRECTIVE_META: Record<string, { label: string; field: string }> = {
  "agentflow-task": { label: "Created task", field: "title" },
  "agentflow-queue": { label: "Queued steps", field: "steps" },
  "agentflow-done": { label: "Task complete", field: "reason" },
  "agentflow-needs-user": { label: "Needs your decision", field: "reason" },
};

/** AgentFlow directive blocks render as action cards instead of raw code. */
function DirectiveCard({ lang, code }: { lang: string; code: string }) {
  const meta = DIRECTIVE_META[lang];
  const fields: Record<string, string> = {};
  for (const line of code.split("\n")) {
    const idx = line.indexOf(":");
    if (idx > 0) fields[line.slice(0, idx).trim().toLowerCase()] = line.slice(idx + 1).trim();
  }
  const steps = (fields.steps ?? (fields.queue === "full" ? "spec → implement → qa → review" : fields.queue) ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return (
    <div className="my-1 rounded-md border border-violet-200 bg-violet-50/70 px-2.5 py-1.5 dark:border-violet-900 dark:bg-violet-950/40">
      <div className="text-[10px] font-semibold uppercase tracking-wide text-violet-600 dark:text-violet-300">
        {meta?.label ?? lang}
      </div>
      {fields.title && <div className="mt-0.5 text-xs font-medium">{fields.title}</div>}
      {fields.reason && <div className="mt-0.5 text-xs">{fields.reason}</div>}
      {fields.goal && <div className="mt-0.5 text-[11px] text-neutral-600 dark:text-neutral-400">{fields.goal}</div>}
      {steps.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {steps.map((s) => (
            <span
              key={s}
              className="rounded border border-violet-300 px-1.5 py-0.5 font-mono text-[10px] text-violet-700 dark:border-violet-800 dark:text-violet-300"
            >
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/** A message body: directive cards + code blocks + light markdown, collapsible when long. */
function MessageBody({ content }: { content: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = content.length > COLLAPSE_CHARS;
  const segments = parseSegments(content);
  return (
    <div>
      <div className={long && !expanded ? "relative max-h-36 overflow-hidden" : ""}>
        {segments.map((seg, i) =>
          seg.kind === "code" ? (
            seg.lang.startsWith("agentflow-") ? (
              <DirectiveCard key={i} lang={seg.lang} code={seg.code} />
            ) : (
              <pre key={i} className="mono-block my-1 max-h-48 whitespace-pre-wrap text-[10px]">
                {seg.code.trim()}
              </pre>
            )
          ) : (
            <TextBlock key={i} text={seg.text.trim()} />
          ),
        )}
        {long && !expanded && (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-white to-transparent dark:from-neutral-800" />
        )}
      </div>
      {long && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="focusable mt-1 cursor-pointer rounded text-[10px] font-medium text-blue-600 hover:underline dark:text-blue-400"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

function Bubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === "system") {
    return (
      <div
        className="flex items-start gap-1.5 rounded-md border border-neutral-200 bg-neutral-50 px-2.5 py-1.5 dark:border-neutral-800 dark:bg-neutral-950/60"
        title={msg.time}
      >
        <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-violet-500" aria-hidden="true" />
        <span className="min-w-0 flex-1 text-[11px] leading-snug text-neutral-600 dark:text-neutral-400">
          {msg.content}
        </span>
      </div>
    );
  }
  const mine = msg.role === "user";
  return (
    <div className={`flex flex-col ${mine ? "items-end" : "items-start"}`}>
      {!mine && msg.provider && (
        <span className="mb-0.5 px-1 font-mono text-[10px] text-neutral-400">
          {msg.provider}
          {msg.durationMs !== undefined && ` · ${(msg.durationMs / 1000).toFixed(1)}s`}
        </span>
      )}
      <div
        title={msg.time}
        className={`max-w-[92%] break-words rounded-lg px-3 py-2 text-xs leading-relaxed ${
          mine
            ? "rounded-br-sm bg-accent text-white"
            : "rounded-bl-sm border border-neutral-200 bg-white text-neutral-800 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200"
        }`}
      >
        {mine ? <span className="whitespace-pre-wrap">{msg.content}</span> : <MessageBody content={msg.content} />}
      </div>
    </div>
  );
}

/* ----------------------------------------------------- live agent activity */

function elapsed(startedAt?: string): string {
  if (!startedAt) return "";
  const s = Math.max(0, Math.round((Date.now() - Date.parse(startedAt)) / 1000));
  return s < 90 ? `${s}s` : `${Math.round(s / 60)}m`;
}

const ACTIVE = ["queued", "awaiting_approval", "blocked", "running"];

function AgentActivity({ queue, running }: { queue: QueueState | null; running: RunInfo[] }) {
  const items = (queue?.items ?? []).filter((i) => ACTIVE.includes(i.status));
  const orchestrating = running.find((r) => r.step === "orchestrate");
  if (items.length === 0 && !orchestrating) return null;
  return (
    <div className="rounded-md border border-blue-200 bg-blue-50/60 px-2.5 py-2 dark:border-blue-900 dark:bg-blue-950/30">
      <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-blue-700 dark:text-blue-300">
        Agents at work
      </div>
      <div className="space-y-1">
        {orchestrating && (
          <div className="flex items-center gap-1.5 text-[11px] text-neutral-700 dark:text-neutral-300">
            <Spinner className="h-3 w-3 text-violet-500" />
            <span className="font-mono">{orchestrating.provider}</span>
            <span>is deciding the next step… {elapsed(orchestrating.startedAt)}</span>
          </div>
        )}
        {items.map((i) => (
          <div key={i.id} className="flex items-center gap-1.5 text-[11px] text-neutral-700 dark:text-neutral-300">
            {i.status === "running" ? (
              <Spinner className="h-3 w-3 text-blue-500" />
            ) : (
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                  i.status === "queued" ? "bg-neutral-400" : "bg-amber-500"
                }`}
                aria-hidden="true"
              />
            )}
            <span className="font-mono">{i.provider}</span>
            <span className="min-w-0 flex-1 truncate">
              {i.status === "running" && `is working on ${i.label}… ${elapsed(i.startedAt)}`}
              {i.status === "queued" && `waiting to run ${i.label}`}
              {(i.status === "blocked" || i.status === "awaiting_approval") &&
                `${i.label} needs approval (Tasks tab)`}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------- panel */

/** Persistent orchestrator chat dock — always available on the right. */
export default function ChatPanel({ workspacePath }: { workspacePath: string | null }) {
  const hasWorkspace = Boolean(workspacePath);
  const [open, setOpen] = useState(() => localStorage.getItem(OPEN_KEY) !== "0");
  const [data, setData] = useState<ChatState | null>(null);
  const [queue, setQueue] = useState<QueueState | null>(null);
  const [running, setRunning] = useState<RunInfo[]>([]);
  const [input, setInput] = useState("");
  const [provider, setProvider] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef(workspacePath);

  const toggle = (next: boolean) => {
    setOpen(next);
    localStorage.setItem(OPEN_KEY, next ? "1" : "0");
  };

  // Each workspace has its own chat — drop everything from the previous one.
  useEffect(() => {
    wsRef.current = workspacePath;
    setData(null);
    setQueue(null);
    setRunning([]);
    setNotice(null);
    setProvider(null);
  }, [workspacePath]);

  const load = useCallback(async () => {
    const ws = workspacePath;
    if (!ws) return;
    try {
      const [chat, q, logs] = await Promise.all([api.chat(), api.queue(), api.logs()]);
      if (wsRef.current !== ws) return; // ignore stale responses
      setData(chat);
      setQueue(q);
      setRunning(logs.running);
    } catch {
      /* backend banner covers outages */
    }
  }, [workspacePath]);

  const busy =
    data?.pending != null ||
    (queue?.items ?? []).some((i) => i.status === "running") ||
    running.some((r) => r.step === "orchestrate");

  // Poll fast while agents are active, slowly otherwise.
  useEffect(() => {
    if (!open || !hasWorkspace) return;
    void load();
    const id = window.setInterval(load, busy ? 2000 : 6000);
    return () => window.clearInterval(id);
  }, [open, hasWorkspace, load, busy]);

  // Stick to the bottom as messages arrive.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [data?.messages.length, data?.pending?.outputTail, busy]);

  const send = async () => {
    const message = input.trim();
    if (!message || sending) return;
    setSending(true);
    setNotice(null);
    try {
      const res = await api.chatSend(message, provider);
      if (res.status === "started") {
        setInput("");
      } else if (res.message) {
        setNotice(res.message);
        if (res.status === "provider_missing") setInput("");
      }
      await load();
    } catch (e) {
      setNotice(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  };

  if (!open) {
    return (
      <div className="flex w-10 shrink-0 flex-col items-center border-l border-neutral-200 bg-white/60 py-2 dark:border-neutral-800 dark:bg-neutral-900/60">
        <button
          onClick={() => toggle(true)}
          title="Open orchestrator chat"
          aria-label="Open orchestrator chat"
          className="focusable cursor-pointer rounded-lg p-2 text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-800 dark:hover:bg-neutral-800 dark:hover:text-neutral-200"
        >
          <ChatBubble className="h-5 w-5" />
        </button>
      </div>
    );
  }

  // Prefer the configured orchestrator, but fall back to an installed CLI.
  const fallback =
    data?.providers.find((p) => p.id === data.defaultProvider && p.installed)?.id ??
    data?.providers.find((p) => p.installed)?.id ??
    data?.defaultProvider ??
    "antigravity";
  const selected = provider ?? fallback;

  return (
    <section
      className="flex w-80 shrink-0 flex-col border-l border-neutral-200 bg-white/60 dark:border-neutral-800 dark:bg-neutral-900/60"
      aria-label="Orchestrator chat"
    >
      {/* header */}
      <div className="flex shrink-0 items-center gap-1.5 border-b border-neutral-200 px-3 py-2 dark:border-neutral-800">
        <ChatBubble className="h-4 w-4 text-accent-subtle" />
        <span className="text-xs font-semibold">Orchestrator</span>
        <select
          className="focusable ml-1 min-w-0 flex-1 cursor-pointer rounded-md border border-neutral-200 bg-white px-1.5 py-0.5 font-mono text-[11px] text-neutral-700 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300"
          value={selected}
          onChange={(e) => setProvider(e.target.value)}
          aria-label="Chat provider"
        >
          {(data?.providers ?? [{ id: selected, installed: true }]).map((p) => (
            <option key={p.id} value={p.id}>
              {p.id}
              {!p.installed ? " (not installed)" : ""}
            </option>
          ))}
        </select>
        <button
          onClick={() => {
            if (window.confirm("Clear the chat history for this workspace?")) {
              void api.chatClear().then(load);
            }
          }}
          title="Clear chat history"
          aria-label="Clear chat history"
          className="focusable cursor-pointer rounded p-1 text-neutral-400 transition-colors hover:bg-neutral-200 hover:text-neutral-700 dark:hover:bg-neutral-700 dark:hover:text-neutral-200"
        >
          <Close className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => toggle(false)}
          title="Collapse chat"
          aria-label="Collapse chat"
          className="focusable cursor-pointer rounded p-1 text-neutral-400 transition-colors hover:bg-neutral-200 hover:text-neutral-700 dark:hover:bg-neutral-700 dark:hover:text-neutral-200"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* messages */}
      <div ref={scrollRef} className="min-h-0 flex-1 space-y-2.5 overflow-y-auto px-3 py-3">
        {!hasWorkspace ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
            <ChatBubble className="h-6 w-6 text-neutral-300 dark:text-neutral-600" />
            <p className="text-xs text-neutral-500">Open a workspace to start chatting with your orchestrator.</p>
          </div>
        ) : data && data.messages.length === 0 && !data.pending ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-2 text-center">
            <ChatBubble className="h-6 w-6 text-neutral-300 dark:text-neutral-600" />
            <p className="text-xs text-neutral-500">
              Ask the orchestrator for work — it creates tasks and cues the agents.
            </p>
          </div>
        ) : (
          data?.messages.map((m, i) => <Bubble key={`${m.time}-${i}`} msg={m} />)
        )}

        <AgentActivity queue={queue} running={running} />

        {data?.pending && (
          <div className="flex flex-col items-start">
            <span className="mb-0.5 flex items-center gap-1 px-1 font-mono text-[10px] text-neutral-400">
              <Spinner className="h-3 w-3" /> thinking…
            </span>
            {data.pending.outputTail && (
              <pre className="max-h-36 w-full overflow-auto whitespace-pre-wrap rounded-lg border border-blue-200 bg-blue-50/60 p-2 font-mono text-[10px] leading-relaxed text-neutral-600 dark:border-blue-900 dark:bg-blue-950/30 dark:text-neutral-300">
                {data.pending.outputTail}
              </pre>
            )}
          </div>
        )}
      </div>

      {/* notice + input */}
      <div className="shrink-0 border-t border-neutral-200 p-2.5 dark:border-neutral-800">
        {notice && (
          <p className="mb-2 rounded-lg bg-amber-50 px-2.5 py-1.5 text-[11px] text-amber-800 dark:bg-amber-950/50 dark:text-amber-300">
            {notice}
          </p>
        )}
        <div className="flex items-end gap-1.5">
          <textarea
            className="input max-h-32 min-h-[38px] flex-1 resize-none text-xs"
            placeholder={hasWorkspace ? "Ask the orchestrator… (Enter to send)" : "Open a workspace first"}
            value={input}
            disabled={!hasWorkspace || sending}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
            rows={Math.min(4, Math.max(1, input.split("\n").length))}
            aria-label="Chat message"
          />
          {data?.pending ? (
            <button
              className="btn-danger shrink-0 px-2.5"
              onClick={() => void api.chatStop().then(load)}
              title="Stop response"
              aria-label="Stop response"
            >
              <StopSquare className="h-4 w-4" />
            </button>
          ) : (
            <button
              className="btn-primary shrink-0 px-2.5"
              onClick={() => void send()}
              disabled={!hasWorkspace || !input.trim() || sending}
              title="Send"
              aria-label="Send message"
            >
              <Send className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
