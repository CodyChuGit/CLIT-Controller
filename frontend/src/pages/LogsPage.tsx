import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import LogConsole from "../components/LogConsole";
import { Card, PageShell } from "../components/ui";
import { useConnection, useRecentEvents, useStructuralRevision } from "../stream";
import type { LogsResponse } from "../types";

const EVENT_DOT: Record<string, string> = {
  run: "bg-blue-500",
  chat: "bg-violet-500",
  controller: "bg-violet-500",
  command: "bg-blue-500",
  queue: "bg-neutral-400",
  approval: "bg-amber-500",
  task: "bg-emerald-500",
  recovery: "bg-rose-500",
};

export default function LogsPage() {
  const [data, setData] = useState<LogsResponse | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const recent = useRecentEvents();
  const connection = useConnection();
  const streamRev = useStructuralRevision();

  const load = useCallback(async () => {
    try {
      setData(await api.logs());
    } catch {
      /* backend offline — sidebar already shows it */
    }
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(load, 3000);
    return () => window.clearInterval(id);
  }, [load, streamRev]);

  const providers = useMemo(() => {
    const set = new Set<string>();
    data?.entries.forEach((e) => e.provider && set.add(e.provider));
    return [...set].sort();
  }, [data]);

  const entries = useMemo(() => {
    if (!data) return [];
    if (filter === "all") return data.entries;
    return data.entries.filter((e) => e.provider === filter);
  }, [data, filter]);

  return (
    <PageShell
      title="Logs"
      actions={
        <>
          <select
            className="select w-40"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            aria-label="Filter by provider"
          >
            <option value="all">All providers</option>
            {providers.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <button className="btn-secondary" onClick={load}>Refresh</button>
          <button
            className="btn-secondary"
            onClick={async () => {
              await api.clearLogView();
              await load();
            }}
          >
            Clear view
          </button>
        </>
      }
    >
      <Card
        title={
          <span className="flex items-center gap-2">
            <span className="section-title">Live events</span>
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                connection === "live" ? "bg-emerald-500" : connection === "polling" ? "bg-amber-500" : "bg-neutral-400"
              }`}
              title={`streaming: ${connection}`}
              aria-hidden="true"
            />
          </span>
        }
      >
        <div className="max-h-72 overflow-y-auto px-3 py-1">
          {recent.length === 0 ? (
            <p className="px-1 py-2 text-xs text-neutral-400">No events yet.</p>
          ) : (
            [...recent].reverse().map((e) => (
              <div key={e.id} className="flex items-start gap-2 border-b border-neutral-100 py-1 last:border-0 dark:border-neutral-800/60">
                <span
                  className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${EVENT_DOT[e.type.split(".")[0]] ?? "bg-neutral-400"}`}
                  aria-hidden="true"
                />
                <span className="w-16 shrink-0 font-mono text-[10px] tabular-nums leading-5 text-neutral-400">
                  {new Date(e.createdAt).toLocaleTimeString()}
                </span>
                <span className="shrink-0 font-mono text-[10px] leading-5 text-neutral-500">{e.type}</span>
                <span className="min-w-0 flex-1 truncate text-xs leading-5 text-neutral-700 dark:text-neutral-300" title={e.detail}>
                  {e.detail}
                </span>
              </div>
            ))
          )}
        </div>
      </Card>

      <Card title="Activity">
        <div className="px-4 py-1">
          <LogConsole entries={entries} running={data?.running ?? []} />
        </div>
      </Card>
    </PageShell>
  );
}
