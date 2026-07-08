import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "../api";
import { Spinner } from "../components/icons";

interface UiState {
  available: boolean;
  running: boolean;
  url: string | null;
}

// The Memory tab embeds codebase-memory-mcp's own graph viewer as-is in an
// iframe (the "galaxy"). The backend starts that sidecar and returns its URL;
// we deep-link to the graph view for the current workspace's project.
export default function MemoryPage() {
  const [ui, setUi] = useState<UiState | null>(null);
  const [project, setProject] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setUi(await api.memoryUi());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
    try {
      const s = await api.memoryStatus();
      setProject(s.project ?? null);
    } catch {
      /* project only scopes the deep-link; never block the viewer on it */
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // The sidecar may take a moment to come up; poll until it's ready.
  useEffect(() => {
    if (!ui?.available || ui.running) return;
    const t = setTimeout(() => void load(), 1500);
    return () => clearTimeout(t);
  }, [ui, load]);

  if (ui && !ui.available) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
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

  const src =
    ui?.running && ui.url
      ? `${ui.url}?tab=graph${project ? `&project=${encodeURIComponent(project)}` : ""}`
      : "";

  return src ? (
    <iframe title="Codebase Memory graph" src={src} className="h-full w-full border-0" />
  ) : (
    <div className="flex h-full flex-col items-center justify-center gap-2 text-neutral-400">
      <Spinner className="h-5 w-5" />
      <span className="text-xs">{error ?? "Starting the graph viewer…"}</span>
    </div>
  );
}
