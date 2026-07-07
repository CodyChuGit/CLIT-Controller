import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "../api";

interface UiState {
  available: boolean;
  running: boolean;
  url: string | null;
}

// The Memory tab embeds codebase-memory-mcp's own graph viewer (the `:9749`
// "galaxy" UI). The backend starts that sidecar and hands back its URL; we
// iframe it so the map is the real thing, not a reimplementation.
export default function MemoryPage() {
  const [ui, setUi] = useState<UiState | null>(null);
  const [indexing, setIndexing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setUi(await api.memoryUi());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onIndex = async () => {
    setIndexing(true);
    setError(null);
    try {
      await api.memoryIndex();
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setIndexing(false);
    }
  };

  if (ui && !ui.available) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center">
        <h2 className="text-sm font-semibold text-neutral-800 dark:text-neutral-200">
          Codebase Memory not installed
        </h2>
        <p className="mt-1 max-w-sm text-xs text-neutral-500">
          The{" "}
          <code className="rounded bg-neutral-100 px-1 py-0.5 dark:bg-neutral-800">
            codebase-memory-mcp
          </code>{" "}
          tool powers this graph. Install it from the <strong>Agents</strong> tab, then reload.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-neutral-200 px-3 py-1.5 dark:border-neutral-800">
        <span className="text-xs font-semibold text-neutral-700 dark:text-neutral-200">
          Codebase Memory
        </span>
        <button className="btn-secondary btn-xs" onClick={onIndex} disabled={indexing}>
          {indexing ? "Indexing…" : "Re-index workspace"}
        </button>
        {ui?.url && (
          <a className="btn-secondary btn-xs" href={ui.url} target="_blank" rel="noreferrer">
            Open in browser ↗
          </a>
        )}
        <button className="btn-secondary btn-xs" onClick={() => void load()}>
          Refresh
        </button>
        {error && <span className="text-[11px] text-amber-600 dark:text-amber-400">{error}</span>}
      </div>
      <div className="min-h-0 flex-1">
        {ui?.running && ui.url ? (
          <iframe title="Codebase Memory graph" src={ui.url} className="h-full w-full border-0" />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-neutral-400">
            {ui ? "Starting the graph viewer…" : "Loading…"}
          </div>
        )}
      </div>
    </div>
  );
}
