import { useState } from "react";
import type { LogEntry, RunInfo } from "../types";
import StatusBadge from "./StatusBadge";

interface Props {
  entries: LogEntry[];
  running?: RunInfo[];
}

function Entry({ entry }: { entry: LogEntry }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-neutral-100 py-2 last:border-0 dark:border-neutral-800">
      <button
        className="flex w-full items-center gap-2 text-left"
        onClick={() => entry.output && setOpen(!open)}
      >
        <span className="w-16 shrink-0 font-mono text-[11px] text-neutral-400">
          {new Date(entry.time).toLocaleTimeString()}
        </span>
        <StatusBadge state={entry.status} label={entry.source} />
        {entry.provider && (
          <span className="rounded bg-neutral-100 px-1.5 py-0.5 font-mono text-[11px] text-neutral-500 dark:bg-neutral-800">
            {entry.provider}
          </span>
        )}
        <span className="min-w-0 flex-1 truncate text-xs text-neutral-700 dark:text-neutral-300">
          {entry.summary}
        </span>
        {entry.output && <span className="text-[11px] text-neutral-400">{open ? "▾" : "▸"}</span>}
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
        <div className="mb-3 space-y-2">
          {running.map((r) => (
            <div key={r.id} className="rounded-xl border border-blue-200 bg-blue-50/60 p-3 dark:border-blue-900 dark:bg-blue-950/30">
              <div className="mb-1 flex items-center gap-2 text-xs">
                <StatusBadge state="running" />
                <span className="font-mono text-neutral-500">{r.provider ?? "process"}</span>
                <span className="truncate text-neutral-500">{r.step ?? r.commandPreview.slice(0, 80)}</span>
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
        <p className="py-8 text-center text-sm text-neutral-400">No log entries yet.</p>
      ) : (
        [...entries].reverse().map((e) => <Entry key={e.id} entry={e} />)
      )}
    </div>
  );
}
