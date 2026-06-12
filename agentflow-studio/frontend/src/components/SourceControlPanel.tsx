import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { GitFileEntry, GitStatus } from "../types";
import { ChevronDown, ChevronRight, GitBranch, Refresh, Spinner } from "./icons";

const CODE_COLORS: Record<string, string> = {
  M: "text-amber-600 dark:text-amber-400",
  A: "text-emerald-600 dark:text-emerald-400",
  U: "text-emerald-600 dark:text-emerald-400",
  D: "text-rose-600 dark:text-rose-400",
  R: "text-blue-600 dark:text-blue-400",
  C: "text-blue-600 dark:text-blue-400",
};

function FileRow({
  entry,
  staged,
  busy,
  onOpenDiff,
  onToggleStage,
}: {
  entry: GitFileEntry;
  staged: boolean;
  busy: boolean;
  onOpenDiff: () => void;
  onToggleStage: () => void;
}) {
  const name = entry.path.split("/").pop() ?? entry.path;
  const dir = entry.path.slice(0, entry.path.length - name.length).replace(/\/$/, "");
  return (
    <div className="group flex items-center gap-1 rounded px-1 py-0.5 hover:bg-neutral-100 dark:hover:bg-neutral-800">
      <button
        onClick={onOpenDiff}
        title={`Open diff: ${entry.path}`}
        className="focusable flex min-w-0 flex-1 cursor-pointer items-center gap-1.5 rounded text-left"
      >
        <span className={`w-3 shrink-0 text-center font-mono text-[11px] font-bold ${CODE_COLORS[entry.code] ?? "text-neutral-500"}`}>
          {entry.code}
        </span>
        <span className="truncate text-xs text-neutral-700 dark:text-neutral-300">{name}</span>
        {dir && <span className="truncate text-[10px] text-neutral-400">{dir}</span>}
      </button>
      <button
        onClick={onToggleStage}
        disabled={busy}
        title={staged ? `Unstage ${name}` : `Stage ${name}`}
        aria-label={staged ? `Unstage ${name}` : `Stage ${name}`}
        className="focusable hidden shrink-0 cursor-pointer rounded px-1 font-mono text-xs text-neutral-400 hover:bg-neutral-200 hover:text-neutral-700 group-hover:block dark:hover:bg-neutral-700 dark:hover:text-neutral-200"
      >
        {staged ? "−" : "+"}
      </button>
    </div>
  );
}

interface Props {
  workspacePath: string;
  onOpenDiff: (path: string, staged: boolean) => void;
}

/** VS Code-style source control: live status, stage/unstage, commit, click-to-diff. */
export default function SourceControlPanel({ workspacePath, onOpenDiff }: Props) {
  const [open, setOpen] = useState(true);
  const [status, setStatus] = useState<GitStatus | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const wsRef = useRef(workspacePath);

  // New workspace, new repo: reset immediately instead of showing the old one.
  useEffect(() => {
    wsRef.current = workspacePath;
    setStatus(null);
    setMessage("");
    setNote(null);
  }, [workspacePath]);

  const load = useCallback(async () => {
    const ws = workspacePath;
    try {
      const s = await api.gitStatus();
      if (wsRef.current === ws) setStatus(s); // ignore stale responses from a previous workspace
    } catch {
      /* workspace/backend issues are surfaced elsewhere */
    }
  }, [workspacePath]);

  // Live, like VS Code: refresh on an interval while the panel is open.
  useEffect(() => {
    if (!open) return;
    void load();
    const id = window.setInterval(load, 5000);
    return () => window.clearInterval(id);
  }, [open, load]);

  const act = async (fn: () => Promise<{ ok: boolean; output: string }>, failNote: string) => {
    setBusy(true);
    setNote(null);
    try {
      const res = await fn();
      if (!res.ok) setNote(`${failNote}: ${res.output.slice(0, 200)}`);
      await load();
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const commit = async () => {
    const msg = message.trim();
    if (!msg) return;
    await act(() => api.gitCommit(msg), "Commit failed");
    setMessage("");
  };

  const staged = status?.staged ?? [];
  const changes = status?.changes ?? [];

  return (
    <div className="shrink-0 border-b border-neutral-200 dark:border-neutral-800">
      <div className="flex items-center">
        <button
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          className="focusable flex flex-1 cursor-pointer items-center gap-1 px-2 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide text-neutral-500 transition-colors hover:text-neutral-800 dark:hover:text-neutral-200"
        >
          {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          Source Control
          {status?.isRepo && (
            <span className="ml-1 flex items-center gap-1 font-mono text-[10px] normal-case text-neutral-500">
              <GitBranch className="h-3 w-3" />
              {status.branch}
              {(status.ahead ?? 0) > 0 && <span className="text-emerald-600 dark:text-emerald-400">↑{status.ahead}</span>}
              {(status.behind ?? 0) > 0 && <span className="text-amber-600 dark:text-amber-400">↓{status.behind}</span>}
            </span>
          )}
        </button>
        {busy && <Spinner className="mr-1 h-3.5 w-3.5 text-neutral-400" />}
        <button
          onClick={() => void load()}
          title="Refresh"
          aria-label="Refresh source control"
          className="focusable mx-1 cursor-pointer rounded p-1 text-neutral-400 transition-colors duration-150 hover:bg-neutral-200 hover:text-neutral-700 dark:hover:bg-neutral-700 dark:hover:text-neutral-200"
        >
          <Refresh className="h-3.5 w-3.5" />
        </button>
      </div>

      {open && (
        <div className="space-y-2 px-2 pb-2.5">
          {!status ? (
            <div className="skeleton h-16" aria-hidden="true" />
          ) : !status.installed ? (
            <p className="px-1 text-xs text-rose-600 dark:text-rose-400">git is not installed.</p>
          ) : !status.isRepo ? (
            <p className="px-1 text-xs text-neutral-500">Not a git repository.</p>
          ) : (
            <>
              <div className="flex gap-1.5">
                <input
                  className="input px-2 py-1.5 text-xs"
                  placeholder={staged.length > 0 ? "Commit message" : "Stage changes to commit"}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void commit();
                  }}
                  aria-label="Commit message"
                />
                <button
                  className="btn-primary shrink-0 px-2.5 py-1 text-xs"
                  disabled={busy || staged.length === 0 || !message.trim()}
                  onClick={() => void commit()}
                  title={staged.length === 0 ? "Stage changes first" : "git commit (⌘↵)"}
                >
                  Commit
                </button>
              </div>
              {note && <p className="px-1 text-[11px] text-rose-600 dark:text-rose-400">{note}</p>}

              {staged.length > 0 && (
                <div>
                  <div className="px-1 py-1 text-[10px] font-semibold uppercase tracking-wide text-neutral-400">
                    Staged Changes ({staged.length})
                  </div>
                  {staged.map((f) => (
                    <FileRow
                      key={`s-${f.path}`}
                      entry={f}
                      staged
                      busy={busy}
                      onOpenDiff={() => onOpenDiff(f.path, true)}
                      onToggleStage={() => void act(() => api.gitUnstage(f.path), "Unstage failed")}
                    />
                  ))}
                </div>
              )}

              <div>
                <div className="flex items-center justify-between px-1 py-1">
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-neutral-400">
                    Changes ({changes.length})
                  </span>
                  {changes.length > 0 && (
                    <button
                      className="focusable cursor-pointer rounded text-[10px] text-blue-600 hover:underline dark:text-blue-400"
                      disabled={busy}
                      onClick={() => void act(() => api.gitStage(null), "Stage all failed")}
                    >
                      Stage All
                    </button>
                  )}
                </div>
                {changes.length === 0 && staged.length === 0 ? (
                  <p className="px-1 pb-1 text-xs text-neutral-500">Working tree clean.</p>
                ) : (
                  changes.map((f) => (
                    <FileRow
                      key={`c-${f.path}`}
                      entry={f}
                      staged={false}
                      busy={busy}
                      onOpenDiff={() => onOpenDiff(f.path, false)}
                      onToggleStage={() => void act(() => api.gitStage(f.path), "Stage failed")}
                    />
                  ))
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
