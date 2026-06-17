import { type ReactNode } from "react";
import { Send, StopSquare } from "./icons";

/* The one prompt composer shared by the controller dock and the Tasks page
   (continuation/retry/reroute). Same shape everywhere: an optional context-chip
   row (traffic-control mode, provider/step, budget/health, references), an
   optional leading control (e.g. engine picker), the prompt box, optional extra
   icon actions, and a send/stop button. See docs/task-controller-io-surface.md
   §Input/Output Alignment Rules. */

export function ComposerChip({
  children,
  dot,
  title,
  mono = false,
}: {
  children: ReactNode;
  dot?: string;
  title?: string;
  mono?: boolean;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-md border border-neutral-200 bg-neutral-50 px-1.5 py-0.5 text-[10px] text-neutral-600 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-400 ${
        mono ? "font-mono" : ""
      }`}
    >
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden="true" />}
      {children}
    </span>
  );
}

export default function Composer({
  value,
  onChange,
  onSend,
  onStop,
  busy = false,
  disabled = false,
  placeholder,
  contextChips,
  leading,
  actions,
  sendTitle = "Send",
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onStop?: () => void;
  /** Show the stop button instead of send (a reply/run is in flight). */
  busy?: boolean;
  disabled?: boolean;
  placeholder?: string;
  contextChips?: ReactNode;
  leading?: ReactNode;
  actions?: ReactNode;
  sendTitle?: string;
}) {
  const canSend = !disabled && !busy && value.trim().length > 0;
  return (
    <div className="space-y-1.5">
      {contextChips && <div className="flex flex-wrap items-center gap-1">{contextChips}</div>}
      <div className="flex items-end gap-1.5">
        {leading}
        <textarea
          className="input max-h-32 min-h-[38px] flex-1 resize-none text-xs"
          placeholder={placeholder}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (canSend) onSend();
            }
          }}
          rows={Math.min(4, Math.max(1, value.split("\n").length))}
          aria-label="Message"
        />
        {actions}
        {busy && onStop ? (
          <button className="btn-danger shrink-0 px-2.5" onClick={onStop} title="Stop" aria-label="Stop">
            <StopSquare className="h-4 w-4" />
          </button>
        ) : (
          <button
            className="btn-primary shrink-0 px-2.5"
            onClick={onSend}
            disabled={!canSend}
            title={sendTitle}
            aria-label={sendTitle}
          >
            <Send className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
