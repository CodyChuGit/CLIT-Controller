import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import LogConsole from "../components/LogConsole";
import type { LogsResponse } from "../types";

export default function LogsPage() {
  const [data, setData] = useState<LogsResponse | null>(null);
  const [filter, setFilter] = useState<string>("all");

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
  }, [load]);

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
    <div className="mx-auto max-w-5xl space-y-4 p-6">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Logs</h1>
          <p className="text-xs text-neutral-500">Redacted activity log — auto-refreshes every 3 seconds.</p>
        </div>
        <div className="flex items-center gap-2">
          <select className="input w-40" value={filter} onChange={(e) => setFilter(e.target.value)}>
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
        </div>
      </header>

      <div className="card overflow-hidden">
        <div className="flex items-center border-b border-neutral-200 px-3 py-1.5 dark:border-neutral-800">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Activity</span>
        </div>
        <div className="px-4 py-1">
          <LogConsole entries={entries} running={data?.running ?? []} />
        </div>
      </div>
      <p className="text-[11px] text-neutral-400">
        Clearing the view does not delete saved log files in task folders.
      </p>
    </div>
  );
}
