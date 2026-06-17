import type { ChatMessage } from "../../types";
import { AntigravityMark, ClaudeMark, OpenAIMark } from "../icons";
import { Markdown, withStepChips } from "../Markdown";
import RawDetail from "../RawDetail";
import { Disclosure } from "../TaskViews";

/* Pillar 4 — the single, canonical chat-message renderer shared by every
   chat-like surface (Agent Dock / ChatPanel, task replay / StepChat, and any
   future conversation view). Extracted from ChatPanel so no surface owns a
   competing message renderer. Surface-specific layout composes these primitives;
   it does not re-implement message presentation. */

export const PROVIDER_DOT: Record<string, string> = {
  codex: "bg-emerald-500",
  claude: "bg-orange-500",
  antigravity: "bg-sky-500",
  shell: "bg-neutral-500",
};

const PROVIDER_TEXT: Record<string, string> = {
  codex: "text-emerald-600 dark:text-emerald-500",
  claude: "text-orange-600 dark:text-orange-500",
  antigravity: "text-sky-600 dark:text-sky-500",
};

const PROVIDER_MARK: Record<string, (p: React.SVGProps<SVGSVGElement>) => JSX.Element> = {
  codex: OpenAIMark,
  claude: ClaudeMark,
  antigravity: AntigravityMark,
};

/** The provider's official mark in its accent color; dot fallback for unknowns. */
export function ProviderMark({ id, className = "h-4 w-4" }: { id: string; className?: string }) {
  const Mark = PROVIDER_MARK[id];
  if (!Mark) {
    return (
      <span
        className={`h-2 w-2 rounded-full ${PROVIDER_DOT[id] ?? "bg-neutral-400"}`}
        aria-hidden="true"
      />
    );
  }
  return <Mark className={`${className} shrink-0 ${PROVIDER_TEXT[id] ?? ""}`} />;
}

/* ----------------------------------------------------------- system notices */

function noticeStyle(content: string): { border: string; dot: string } {
  if (content.startsWith("$")) return { border: "border-l-neutral-400", dot: "bg-neutral-500" };
  if (/complete —|complete:/.test(content))
    return { border: "border-l-emerald-500", dot: "bg-emerald-500" };
  if (/^(Needs|Manual|Didn)/.test(content))
    return { border: "border-l-amber-500", dot: "bg-amber-500" };
  if (/^Created/.test(content)) return { border: "border-l-blue-500", dot: "bg-blue-500" };
  if (/^(Queued|Reviewed|Controller|Orchestrator)/.test(content))
    return { border: "border-l-violet-500", dot: "bg-violet-500" };
  return { border: "border-l-neutral-300 dark:border-l-neutral-600", dot: "bg-neutral-400" };
}

export function SystemNotice({ msg }: { msg: ChatMessage }) {
  const style = noticeStyle(msg.content);
  const [first, ...rest] = msg.content.split("\n");
  return (
    <div
      className={`rounded-md border border-l-2 border-neutral-200 bg-white px-2.5 py-1.5 dark:border-neutral-800 dark:bg-neutral-900 ${style.border}`}
      title={msg.time}
    >
      <div className="flex items-start gap-1.5">
        <span
          className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${style.dot}`}
          aria-hidden="true"
        />
        <span
          className={`min-w-0 flex-1 text-[11px] leading-snug text-neutral-700 dark:text-neutral-300 ${first.startsWith("$") ? "font-mono" : ""}`}
        >
          {withStepChips(first)}
        </span>
      </div>
      {rest.length > 0 &&
        (rest.join("\n").length > 400 ? (
          // Long raw tail → the shared paginated viewer (same component the Tasks
          // page uses), behind an expander so the notice stays compact.
          <Disclosure label="View raw" className="mt-1 pl-3">
            <RawDetail text={rest.join("\n")} kind="log" pageSize={50} />
          </Disclosure>
        ) : (
          <pre className="mt-1 max-h-24 overflow-auto whitespace-pre-wrap pl-3 font-mono text-[10px] text-neutral-500 dark:text-neutral-400">
            {rest.join("\n")}
          </pre>
        ))}
    </div>
  );
}

/** One conversation message. `direct` keeps a failed provider turn in its own
    attributed bubble (direct chats) rather than the controller's notice strip. */
export function Message({ msg, direct = false }: { msg: ChatMessage; direct?: boolean }) {
  if (msg.role === "system" && !direct) return <SystemNotice msg={msg} />;
  const mine = msg.role === "user";
  const failed = msg.role === "system";
  return (
    <div className={`flex flex-col ${mine ? "items-end" : "items-start"}`}>
      {!mine && msg.provider && (
        <span className="mb-0.5 flex items-center gap-1.5 px-1 text-[10px] text-neutral-400">
          <ProviderMark id={msg.provider} className="h-3 w-3" />
          <span className="font-mono">{msg.provider}</span>
          {failed ? (
            <span className="text-rose-500">failed</span>
          ) : (
            msg.durationMs !== undefined && (
              <span className="tabular-nums">{(msg.durationMs / 1000).toFixed(1)}s</span>
            )
          )}
        </span>
      )}
      <div
        title={msg.time}
        className={`max-w-[94%] break-words rounded-lg px-3 py-2 text-xs leading-relaxed ${
          mine
            ? "rounded-br-sm bg-accent text-white"
            : "rounded-bl-sm border border-neutral-200 bg-white text-neutral-800 shadow-sm dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200"
        }`}
      >
        {mine ? (
          <span className="whitespace-pre-wrap">{msg.content}</span>
        ) : (
          <Markdown content={msg.content} />
        )}
      </div>
    </div>
  );
}
