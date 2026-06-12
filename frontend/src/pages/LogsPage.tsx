import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import LogConsole from "../components/LogConsole";
import { Card, PageShell } from "../components/ui";
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
      <Card title="Activity">
        <div className="px-4 py-1">
          <LogConsole entries={entries} running={data?.running ?? []} />
        </div>
      </Card>
    </PageShell>
  );
}
