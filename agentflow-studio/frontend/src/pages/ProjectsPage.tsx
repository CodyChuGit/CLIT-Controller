import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import CodeReader from "../components/CodeReader";
import FileTree from "../components/FileTree";
import StatusBadge from "../components/StatusBadge";
import type { CurrentProject, FileContent, GitInfo, Tree } from "../types";

interface Props {
  project: CurrentProject | null;
  onProjectChange: () => void;
}

export default function ProjectsPage({ project, onProjectChange }: Props) {
  const [pathInput, setPathInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tree, setTree] = useState<Tree | null>(null);
  const [git, setGit] = useState<GitInfo | null>(null);
  const [file, setFile] = useState<FileContent | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const hasWorkspace = Boolean(project?.workspacePath);

  const refresh = useCallback(async () => {
    if (!hasWorkspace) return;
    try {
      const [t, g] = await Promise.all([api.tree(), api.git()]);
      setTree(t);
      setGit(g);
    } catch (e) {
      setError(String(e));
    }
  }, [hasWorkspace]);

  useEffect(() => {
    setPathInput(project?.workspacePath ?? "");
    void refresh();
  }, [project?.workspacePath, refresh]);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.setWorkspace(pathInput.trim());
      onProjectChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const openFile = async (path: string) => {
    setSelected(path);
    setFileError(null);
    try {
      setFile(await api.file(path));
    } catch (e) {
      setFile(null);
      setFileError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="space-y-5 p-8">
      <header>
        <h1 className="text-xl font-semibold">Projects</h1>
        <p className="text-sm text-neutral-500">Choose a workspace folder for AgentFlow to orchestrate.</p>
      </header>

      <div className="card p-5">
        <label className="label">Workspace folder path</label>
        <div className="flex gap-2">
          <input
            className="input font-mono"
            placeholder="/Users/you/code/my-project"
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void save()}
          />
          <button className="btn-primary shrink-0" onClick={save} disabled={saving || !pathInput.trim()}>
            {saving ? "Saving…" : "Save workspace"}
          </button>
          {hasWorkspace && (
            <button className="btn-secondary shrink-0" onClick={() => void api.openWorkspaceFolder()}>
              Open in Finder
            </button>
          )}
        </div>
        <p className="mt-2 text-[11px] text-neutral-500 dark:text-neutral-400">
          Local folder path is resolved by the Python backend. Saving creates{" "}
          <code className="font-mono">.agentflow/</code> inside the workspace.
        </p>
        {error && (
          <p className="mt-2 text-xs text-rose-600 dark:text-rose-400" role="alert">
            {error}
          </p>
        )}
        {hasWorkspace && (
          <p className="mt-2 truncate text-xs text-neutral-500">
            Current: <code className="font-mono">{project?.workspacePath}</code>
          </p>
        )}
      </div>

      {hasWorkspace && (
        <>
          <div className="card p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Git</h2>
              <div className="flex items-center gap-2">
                {git?.isRepo && <StatusBadge state="ok" label={`branch ${git.branch}`} />}
                <button className="btn-secondary" onClick={refresh}>Refresh</button>
              </div>
            </div>
            {!git ? (
              <div className="grid gap-4 md:grid-cols-2" aria-hidden="true">
                <div className="skeleton h-24" />
                <div className="skeleton h-24" />
              </div>
            ) : !git.installed ? (
              <p className="text-sm text-rose-500">git is not installed.</p>
            ) : !git.isRepo ? (
              <p className="text-sm text-neutral-500">This folder is not a git repository.</p>
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <div className="label">git status --short</div>
                  <pre className="mono-block max-h-44 whitespace-pre-wrap">{git.statusShort || "clean"}</pre>
                </div>
                <div>
                  <div className="label">git diff --stat</div>
                  <pre className="mono-block max-h-44 whitespace-pre-wrap">{git.diffStat || "no unstaged changes"}</pre>
                </div>
              </div>
            )}
          </div>

          <div className="card grid min-h-[420px] grid-cols-[260px_1fr] overflow-hidden" style={{ height: "52vh" }}>
            <div className="overflow-auto border-r border-neutral-200 dark:border-neutral-800">
              <div className="flex items-center justify-between border-b border-neutral-200 px-3 py-2.5 dark:border-neutral-800">
                <span className="text-xs font-semibold">Files {tree ? `(${tree.fileCount})` : ""}</span>
              </div>
              {tree ? (
                <FileTree nodes={tree.children} onOpenFile={openFile} selected={selected} truncated={tree.truncated} />
              ) : (
                <div className="space-y-2 p-3" aria-hidden="true">
                  {[0, 1, 2, 3, 4].map((i) => (
                    <div key={i} className="skeleton h-5" style={{ width: `${85 - i * 9}%` }} />
                  ))}
                </div>
              )}
            </div>
            <CodeReader
              path={selected}
              content={file?.content ?? null}
              size={file?.size}
              truncated={file?.truncated}
              error={fileError}
            />
          </div>
        </>
      )}
    </div>
  );
}
