import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import ActivityBar, { type PageId } from "./components/ActivityBar";
import AgentDock from "./components/dock/AgentDock";
import { ErrorBoundary } from "./components/ErrorBoundary";
import StatusBar from "./components/StatusBar";
import { loadState, saveState } from "./persist";
import { EventStreamProvider } from "./stream";

const PAGE_IDS: PageId[] = [
  "projects",
  "agents",
  "tasks",
  "preview",
  "usage",
  "logs",
  "memory",
  "sources",
  "settings",
];
import AgentsPage from "./pages/AgentsPage";
import LogsPage from "./pages/LogsPage";
import PreviewPage from "./pages/PreviewPage";
import ProjectsPage from "./pages/ProjectsPage";
import SettingsPage from "./pages/SettingsPage";
import SourcesPage from "./pages/SourcesPage";
import TasksPage from "./pages/TasksPage";
import UsagePage from "./pages/UsagePage";
import type { CurrentProject, EditorFile, GitInfo, Usage } from "./types";

// Lazy — pulls in three.js; keep it out of the initial bundle.
const MemoryPage = lazy(() => import("./pages/MemoryPage"));

export default function App() {
  const [page, setPageState] = useState<PageId>(() => {
    const saved = loadState<PageId>("page", "projects");
    return PAGE_IDS.includes(saved) ? saved : "projects";
  });
  const setPage = useCallback((next: PageId) => {
    setPageState(next);
    saveState("page", next);
  }, []);
  const [project, setProject] = useState<CurrentProject | null>(null);
  const [backendUp, setBackendUp] = useState(true);
  const [git, setGit] = useState<GitInfo | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [queuedCount, setQueuedCount] = useState(0);

  // Editor tabs live here so open files survive page switches.
  const [openFiles, setOpenFiles] = useState<EditorFile[]>([]);
  const [activePath, setActivePath] = useState<string | null>(null);
  // Unsaved editor edits, keyed by path — survive tab/page switches until saved.
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const setDraft = useCallback((path: string, content: string) => {
    setDrafts((prev) => ({ ...prev, [path]: content }));
  }, []);
  const clearDraft = useCallback((path: string) => {
    setDrafts((prev) => {
      if (!(path in prev)) return prev;
      const next = { ...prev };
      delete next[path];
      return next;
    });
  }, []);

  const saveFile = useCallback(
    async (path: string, content: string) => {
      const saved = await api.saveFile(path, content);
      setOpenFiles((prev) =>
        prev.map((f) =>
          f.path === path
            ? {
                ...f,
                content: saved.content,
                size: saved.size,
                truncated: saved.truncated,
                error: undefined,
              }
            : f,
        ),
      );
      clearDraft(path);
    },
    [clearDraft],
  );

  const loadProject = useCallback(async () => {
    try {
      await api.health();
      setBackendUp(true);
      setProject(await api.current());
    } catch {
      setBackendUp(false);
    }
  }, []);

  // Guard against in-flight responses from a previous workspace landing late.
  const wsRef = useRef<string | null>(null);
  useEffect(() => {
    wsRef.current = project?.workspacePath ?? null;
  }, [project?.workspacePath]);

  const refreshShell = useCallback(async () => {
    const ws = project?.workspacePath ?? null;
    if (!ws) {
      setGit(null);
      setUsage(null);
      setQueuedCount(0);
      return;
    }
    try {
      const [g, u, q] = await Promise.all([api.git(), api.usage(), api.queue()]);
      if (wsRef.current === ws) {
        setGit(g);
        setUsage(u);
        setQueuedCount(q.activeCount);
      }
    } catch {
      /* workspace cleared or backend briefly away — status bar shows what it has */
    }
  }, [project?.workspacePath]);

  useEffect(() => {
    void loadProject();
  }, [loadProject]);

  // Status-bar data: refresh on workspace/page change and on a slow interval.
  useEffect(() => {
    void refreshShell();
    const id = window.setInterval(refreshShell, 20_000);
    return () => window.clearInterval(id);
  }, [refreshShell, page]);

  // Switching workspaces invalidates per-workspace shell data, then restores that
  // workspace's remembered editor tabs (paths only — contents are re-read fresh).
  const restoringRef = useRef(false);
  useEffect(() => {
    setOpenFiles([]);
    setActivePath(null);
    setDrafts({});
    setGit(null);
    setUsage(null);
    const ws = project?.workspacePath;
    if (!ws) return;
    const saved = loadState<{ paths: string[]; active: string | null }>(`tabs:${ws}`, {
      paths: [],
      active: null,
    });
    if (saved.paths.length === 0) return;
    restoringRef.current = true;
    void (async () => {
      const files: EditorFile[] = [];
      for (const path of saved.paths) {
        try {
          files.push(await api.file(path));
        } catch {
          /* file disappeared since last session — drop the tab */
        }
      }
      restoringRef.current = false;
      if (wsRef.current !== ws) return; // workspace changed again mid-restore
      setOpenFiles(files);
      setActivePath(
        saved.active && files.some((f) => f.path === saved.active)
          ? saved.active
          : (files[files.length - 1]?.path ?? null),
      );
    })();
  }, [project?.workspacePath]);

  // Remember open tabs (skip transient diff views) for the next session.
  useEffect(() => {
    const ws = project?.workspacePath;
    if (!ws || restoringRef.current) return;
    saveState(`tabs:${ws}`, {
      paths: openFiles.filter((f) => f.kind !== "diff").map((f) => f.path),
      active: activePath,
    });
  }, [openFiles, activePath, project?.workspacePath]);

  const openFile = useCallback(async (path: string) => {
    setActivePath(path);
    try {
      const f = await api.file(path);
      setOpenFiles((prev) => (prev.some((p) => p.path === path) ? prev : [...prev, f]));
    } catch (e) {
      const error = e instanceof Error ? e.message : String(e);
      setOpenFiles((prev) =>
        prev.some((p) => p.path === path) ? prev : [...prev, { path, content: null, error }],
      );
    }
  }, []);

  // Open a git diff as an editor tab (refreshes in place when reopened).
  const openDiff = useCallback(async (path: string, staged: boolean) => {
    const key = `${path} ${staged ? "(staged)" : "(diff)"}`;
    setActivePath(key);
    let file: EditorFile;
    try {
      const d = await api.gitFileDiff(path, staged);
      file = {
        path: key,
        content: d.diff.trim() ? d.diff : "(no diff content)",
        kind: "diff",
        size: d.diff.length,
        truncated: d.truncated,
      };
    } catch (e) {
      file = {
        path: key,
        content: null,
        kind: "diff",
        error: e instanceof Error ? e.message : String(e),
      };
    }
    setOpenFiles((prev) => {
      const i = prev.findIndex((f) => f.path === key);
      if (i >= 0) {
        const next = [...prev];
        next[i] = file;
        return next;
      }
      return [...prev, file];
    });
  }, []);

  const closeFile = useCallback(
    (path: string) => {
      setOpenFiles((prev) => {
        const next = prev.filter((f) => f.path !== path);
        if (activePath === path) {
          setActivePath(next.length > 0 ? next[next.length - 1].path : null);
        }
        return next;
      });
      clearDraft(path);
    },
    [activePath, clearDraft],
  );

  const needsWorkspace =
    page !== "projects" && page !== "agents" && page !== "settings" && !project?.workspacePath;

  return (
    <EventStreamProvider workspacePath={project?.workspacePath ?? null}>
      <div className="flex h-screen flex-col bg-surface font-sans text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
        <a
          href="#main"
          className="focusable absolute left-2 top-2 z-50 -translate-y-16 rounded-lg bg-accent px-3 py-1.5 text-sm text-white transition-transform focus:translate-y-0"
        >
          Skip to content
        </a>

        <div className="flex min-h-0 flex-1">
          <ActivityBar page={page} onNavigate={setPage} />

          <main id="main" className="min-w-0 flex-1 overflow-y-auto">
            {!backendUp && (
              <div className="border-b border-rose-200 bg-rose-50 px-8 py-2.5 text-xs text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">
                Backend not reachable at http://localhost:8787 — start it with{" "}
                <code className="font-mono">./scripts/dev.sh</code>
                <button
                  className="focusable ml-3 cursor-pointer rounded underline"
                  onClick={loadProject}
                >
                  Retry
                </button>
              </div>
            )}

            {needsWorkspace ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
                <p className="text-sm text-neutral-500">No workspace selected yet.</p>
                <button className="btn-primary" onClick={() => setPage("projects")}>
                  Choose a workspace
                </button>
              </div>
            ) : (
              // Per-view boundary keyed on `page`: a crash in one view shows a
              // recoverable fallback instead of blanking the IDE, and navigating
              // to another view resets it (audit P1-08).
              <ErrorBoundary key={page} label="this view">
                {page === "projects" && (
                  <ProjectsPage
                    project={project}
                    onProjectChange={loadProject}
                    openFiles={openFiles}
                    activePath={activePath}
                    drafts={drafts}
                    onOpenFile={openFile}
                    onOpenDiff={openDiff}
                    onCloseFile={closeFile}
                    onActivateFile={setActivePath}
                    onDraftChange={setDraft}
                    onSaveFile={saveFile}
                  />
                )}
                {page === "agents" && <AgentsPage />}
                {page === "tasks" && <TasksPage />}
                {page === "preview" && <PreviewPage />}
                {page === "usage" && <UsagePage />}
                {page === "logs" && <LogsPage />}
                {page === "memory" && (
                  <Suspense
                    fallback={<div className="p-4 text-xs text-neutral-400">Loading graph…</div>}
                  >
                    <MemoryPage />
                  </Suspense>
                )}
                {page === "sources" && <SourcesPage />}
                {page === "settings" && <SettingsPage />}
              </ErrorBoundary>
            )}
          </main>

          <ErrorBoundary label="the agent dock">
            <AgentDock
              workspacePath={project?.workspacePath ?? null}
              project={project}
              git={git}
              usage={usage}
              onNavigate={setPage}
            />
          </ErrorBoundary>
        </div>

        <StatusBar
          backendUp={backendUp}
          project={project}
          git={git}
          usage={usage}
          queuedCount={queuedCount}
          onNavigate={setPage}
        />
      </div>
    </EventStreamProvider>
  );
}
