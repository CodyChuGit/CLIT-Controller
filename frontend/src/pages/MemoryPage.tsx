import { Suspense, lazy, useCallback, useEffect, useState } from "react";

import { api, ApiError } from "../api";
import { Spinner } from "../components/icons";

// three.js / R3F only loads when the Memory tab is actually opened.
const MemoryGalaxy = lazy(() => import("./MemoryGalaxy"));

interface Status {
  available: boolean;
  project: string | null;
}

const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

// The Memory tab renders codebase-memory-mcp's own galaxy (its three.js
// GraphScene component, vendored) natively inside CLITC — fed by the backend
// layout proxy, scoped to the current workspace. No iframe, no viewer chrome.
export default function MemoryPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const [indexing, setIndexing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const s = await api.memoryStatus();
      setStatus({ available: s.available, project: s.project ?? null });
    } catch (e) {
      setError(errMsg(e));
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
      setError(errMsg(e));
    } finally {
      setIndexing(false);
    }
  };

  if (status && !status.available) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-1 p-6 text-center">
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

  if (status && !status.project) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="max-w-xs text-xs text-neutral-400">
          This workspace isn&apos;t indexed yet. Build its knowledge graph to explore it.
        </p>
        <button className="btn-secondary btn-xs" onClick={onIndex} disabled={indexing}>
          {indexing ? "Indexing…" : "Index workspace"}
        </button>
        {error && <p className="text-[11px] text-amber-600 dark:text-amber-400">{error}</p>}
      </div>
    );
  }

  if (!status) {
    return (
      <div className="flex h-full items-center justify-center text-neutral-400">
        <Spinner className="h-5 w-5" />
      </div>
    );
  }

  return (
    <div className="h-full w-full">
      <Suspense
        fallback={
          <div className="flex h-full w-full items-center justify-center bg-[#06090f] text-neutral-400">
            <Spinner className="h-5 w-5" />
          </div>
        }
      >
        <MemoryGalaxy />
      </Suspense>
    </div>
  );
}
