import { useState } from "react";
import type { LogEntry, RunInfo } from "../types";
import { ChevronDown, ChevronRight, Inbox } from "./icons";
import StatusBadge from "./StatusBadge";

interface Props {
  entries: LogEntry[];
  running?: RunInfo[];
}

function Entry({ entry }: { entry: LogEntry }) {
  const [open, setOpen] = useState(false);
  const expandable = Boolean(entry.output);
  return (
    <div className="border-b border-neutral-100 py-2 last:border-0 dark:border-neutral-800">
      <button
        className={`focusable flex w-full items-center gap-2 rounded text-left ${expandable ? "cursor-pointer" : "cursor-default"}`}
        onClick={() => expandable && setOpen(!open)}
        aria-expanded={expandable ? open : undefined}
        disabled={!expandable}
      >
        <span className="w-16 shrink-0 font-mono text-[11px] tabular-nums text-neutral-500">
          {new Date(entry.time).toLocaleTimeString()}
        </span>
        <StatusBadge state={entry.status} label={entry.source} />
        {entry.provider && <span className="chip">{entry.provider}</span>}
        <span className="min-w-0 flex-1 truncate text-xs text-neutral-700 dark:text-neutral-300">
          {entry.summary}
        </span>
        {expandable &&
          (open ? (
            <ChevronDown className="h-3 w-3 shrink-0 text-neutral-400" />
          ) : (
            <ChevronRight className="h-3 w-3 shrink-0 text-neutral-400" />
          ))}
      </button>
      {open && entry.output && (
        <pre className="mono-block mt-2 max-h-64 whitespace-pre-wrap">{entry.output}</pre>
      )}
    </div>
  );
}

export default function LogConsole({ entries, running = [] }: Props) {
  return (
    <div>
      {running.length > 0 && (
        <div className="mb-3 space-y-2" aria-live="polite">
          {running.map((r) => (
            <div
              key={r.id}
              className="rounded-lg border border-blue-200 bg-blue-50/60 p-3 dark:border-blue-900 dark:bg-blue-950/30"
            >
              <div className="mb-1 flex items-center gap-2 text-xs">
                <StatusBadge state="running" />
                <span className="chip">{r.provider ?? "process"}</span>
                <span className="truncate text-neutral-600 dark:text-neutral-400">
                  {r.step ?? r.commandPreview.slice(0, 80)}
                </span>
              </div>
              {(r.stdout || r.stderr) && (
                <pre className="mono-block max-h-40 whitespace-pre-wrap">
                  {r.stdout.slice(-2000)}
                  {r.stderr && `\n${r.stderr.slice(-1000)}`}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
      {entries.length === 0 && running.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-10 text-center">
          <Inbox className="h-6 w-6 text-neutral-300 dark:text-neutral-600" />
          <p className="text-sm text-neutral-500">No log entries yet.</p>
          <p className="text-xs text-neutral-400">
            Check an agent or run a task step to see activity here.
          </p>
        </div>
      ) : (
        [...entries].reverse().map((e) => <Entry key={e.id} entry={e} />)
      )}
    </div>
  );
}
