import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { ChevronDown, ChevronRight, Refresh, StopSquare } from "../components/icons";
import type { PreviewState } from "../types";

/** Embedded browser for the workspace's frontend; AgentFlow can run the dev server. */
export default function PreviewPage() {
  const [state, setState] = useState<PreviewState | null>(null);
  const [reachable, setReachable] = useState<boolean | null>(null);
  const [urlInput, setUrlInput] = useState("");
  const [cmdInput, setCmdInput] = useState("");
  const [frameKey, setFrameKey] = useState(0);
  const [showOutput, setShowOutput] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([api.preview(), api.previewCheck()]);
      setState(s);
      setReachable(c.ok);
      setUrlInput((cur) => cur || s.url);
      setCmdInput((cur) => cur || s.command);
    } catch {
      /* no workspace */
    }
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(load, 4000);
    return () => window.clearInterval(id);
  }, [load]);

  const saveUrl = async () => {
    const url = urlInput.trim();
    if (!url || url === state?.url) return;
    try {
      setState(await api.previewSetUrl(url));
      setFrameKey((k) => k + 1);
      setNotice(null);
    } catch (e) {
      setNotice(e instanceof Error ? e.message : String(e));
    }
  };

  const start = async () => {
    setNotice(null);
    const res = await api.previewStart(cmdInput.trim() || undefined);
    if (res.status === "error") setNotice(res.message ?? "Could not start.");
    await load();
  };

  const stop = async () => {
    await api.previewStop();
    await load();
  };

  return (
    <div className="flex h-full flex-col">
      {/* toolbar */}
      <div className="flex shrink-0 flex-wrap items-center gap-1.5 border-b border-neutral-200 px-3 py-1.5 dark:border-neutral-800">
        {state?.running ? (
          <button className="btn-danger btn-xs" onClick={() => void stop()}>
            <StopSquare className="h-3 w-3" /> Stop
          </button>
        ) : (
          <button className="btn-primary btn-xs" onClick={() => void start()}>
            Start
          </button>
        )}
        <input
          className="input w-44 px-2 py-0.5 font-mono text-[11px]"
          value={cmdInput}
          onChange={(e) => setCmdInput(e.target.value)}
          disabled={state?.running}
          title="Dev server command (runs in the workspace)"
          aria-label="Dev server command"
        />
        <input
          className="input min-w-0 flex-1 px-2 py-0.5 font-mono text-[11px]"
          value={urlInput}
          onChange={(e) => setUrlInput(e.target.value)}
          onBlur={() => void saveUrl()}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          aria-label="Preview URL"
        />
        <span
          className={`h-2 w-2 shrink-0 rounded-full ${reachable ? "bg-emerald-500" : "bg-neutral-300 dark:bg-neutral-700"}`}
          title={reachable ? "App is responding" : "Nothing responding at this URL"}
          aria-hidden="true"
        />
        <button
          onClick={() => setFrameKey((k) => k + 1)}
          title="Reload preview"
          aria-label="Reload preview"
          className="icon-btn"
        >
          <Refresh className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => window.open(state?.url ?? urlInput, "_blank")}
          className="btn-secondary btn-xs"
        >
          Open
        </button>
      </div>

      {notice && (
        <p className="border-b border-amber-200 bg-amber-50 px-3 py-1.5 text-[11px] text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
          {notice}
        </p>
      )}

      {/* the app */}
      <div className="min-h-0 flex-1 bg-white">
        {reachable ? (
          <iframe
            key={frameKey}
            src={state?.url}
            title="App preview"
            className="h-full w-full border-0"
            sandbox="allow-scripts allow-same-origin allow-forms allow-modals"
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 bg-surface text-center dark:bg-neutral-950">
            <p className="text-sm text-neutral-500">
              Nothing responding at <span className="font-mono text-xs">{state?.url ?? "…"}</span>
            </p>
            {!state?.running && (
              <button className="btn-primary" onClick={() => void start()}>
                Start dev server
              </button>
            )}
            {state?.running && <p className="text-xs text-neutral-400">Server starting…</p>}
          </div>
        )}
      </div>

      {/* server output */}
      <div className="shrink-0 border-t border-neutral-200 dark:border-neutral-800">
        <button
          onClick={() => setShowOutput(!showOutput)}
          aria-expanded={showOutput}
          className="focusable flex w-full cursor-pointer items-center gap-1 px-3 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide text-neutral-500 transition-colors hover:text-neutral-800 dark:hover:text-neutral-200"
        >
          {showOutput ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          Server output
          {state?.running && <span className="ml-1 h-1.5 w-1.5 rounded-full bg-emerald-500" aria-hidden="true" />}
        </button>
        {showOutput && (
          <pre className="mono-block max-h-48 overflow-auto whitespace-pre-wrap rounded-none border-t border-neutral-100 text-[10px] dark:border-neutral-800">
            {state?.output || "(no output yet)"}
          </pre>
        )}
      </div>
    </div>
  );
}
