import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { ChatMessage, ChatState } from "../types";
import { ChatBubble, ChevronRight, Close, Send, Spinner, StopSquare } from "./icons";

const OPEN_KEY = "agentflow.chatOpen";

function Bubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === "system") {
    return (
      <div className="px-2 py-1 text-center text-[11px] italic text-neutral-500" title={msg.time}>
        {msg.content}
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
        className={`max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-3 py-2 text-xs leading-relaxed ${
          mine
            ? "rounded-br-sm bg-accent text-white"
            : "rounded-bl-sm border border-neutral-200 bg-white text-neutral-800 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200"
        }`}
      >
        {msg.content}
      </div>
    </div>
  );
}

/** Persistent orchestrator chat dock — always available on the left. */
export default function ChatPanel({ hasWorkspace }: { hasWorkspace: boolean }) {
  const [open, setOpen] = useState(() => localStorage.getItem(OPEN_KEY) !== "0");
  const [data, setData] = useState<ChatState | null>(null);
  const [input, setInput] = useState("");
  const [provider, setProvider] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const toggle = (next: boolean) => {
    setOpen(next);
    localStorage.setItem(OPEN_KEY, next ? "1" : "0");
  };

  const load = useCallback(async () => {
    if (!hasWorkspace) return;
    try {
      setData(await api.chat());
    } catch {
      /* backend banner covers outages */
    }
  }, [hasWorkspace]);

  // Poll fast while a reply is streaming in, slowly otherwise.
  useEffect(() => {
    if (!open || !hasWorkspace) return;
    void load();
    const id = window.setInterval(load, data?.pending ? 1500 : 6000);
    return () => window.clearInterval(id);
  }, [open, hasWorkspace, load, data?.pending !== null]);

  // Stick to the bottom as messages arrive.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [data?.messages.length, data?.pending?.outputTail]);

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
              Chat with your orchestration model — plan work, decide routing, interpret agent results. Ask it
              to create a task and it appears on the Tasks tab.
            </p>
            <p className="text-[11px] text-neutral-400">
              Runs your own <span className="font-mono">{selected}</span> CLI. History is saved in the workspace.
            </p>
          </div>
        ) : (
          data?.messages.map((m, i) => <Bubble key={`${m.time}-${i}`} msg={m} />)
        )}

        {data?.pending && (
          <div className="flex flex-col items-start">
            <span className="mb-0.5 flex items-center gap-1 px-1 font-mono text-[10px] text-neutral-400">
              <Spinner className="h-3 w-3" /> thinking…
            </span>
            {data.pending.outputTail && (
              <pre className="max-h-36 w-full overflow-auto whitespace-pre-wrap rounded-xl border border-blue-200 bg-blue-50/60 p-2 font-mono text-[10px] leading-relaxed text-neutral-600 dark:border-blue-900 dark:bg-blue-950/30 dark:text-neutral-300">
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
