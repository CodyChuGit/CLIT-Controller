import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "../api";
import { Spinner } from "../components/icons";
import { GraphScene } from "../vendor/galaxy/components/GraphScene";
import type { GraphData } from "../vendor/galaxy/lib/types";

const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

// Lazy-loaded so the three.js / R3F bundle only loads when the Memory tab opens.
// Renders codebase-memory-mcp's own galaxy component (vendored GraphScene) for
// the current workspace, fed by the backend's /api/memory/layout proxy — no
// iframe, no viewer chrome.
export default function MemoryGalaxy() {
  const [data, setData] = useState<GraphData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setData(null);
    try {
      setData(await api.memoryLayout());
    } catch (e) {
      setError(errMsg(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-[#06090f] p-6 text-center text-xs text-neutral-400">
        {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-[#06090f] text-neutral-400">
        <Spinner className="h-5 w-5" />
        <span className="text-xs">Loading the galaxy…</span>
      </div>
    );
  }

  return (
    <div className="h-full w-full bg-[#06090f]">
      <GraphScene
        data={data}
        highlightedIds={null}
        cameraTarget={null}
        showLabels
        onNodeClick={() => {}}
      />
    </div>
  );
}
