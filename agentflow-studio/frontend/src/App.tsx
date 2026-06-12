import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import ActivityBar, { type PageId } from "./components/ActivityBar";
import ChatPanel from "./components/ChatPanel";
import StatusBar from "./components/StatusBar";
import AgentsPage from "./pages/AgentsPage";
import LogsPage from "./pages/LogsPage";
import ProjectsPage from "./pages/ProjectsPage";
import SettingsPage from "./pages/SettingsPage";
import TasksPage from "./pages/TasksPage";
import UsagePage from "./pages/UsagePage";
import type { CurrentProject, EditorFile, GitInfo, Usage } from "./types";

export default function App() {
  const [page, setPage] = useState<PageId>("projects");
  const [project, setProject] = useState<CurrentProject | null>(null);
  const [backendUp, setBackendUp] = useState(true);
  const [git, setGit] = useState<GitInfo | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);

  // Editor tabs live here so open files survive page switches.
  const [openFiles, setOpenFiles] = useState<EditorFile[]>([]);
  const [activePath, setActivePath] = useState<string | null>(null);

  const loadProject = useCallback(async () => {
    try {
      await api.health();
      setBackendUp(true);
      setProject(await api.current());
    } catch {
      setBackendUp(false);
    }
  }, []);

  const refreshShell = useCallback(async () => {
    if (!project?.workspacePath) {
      setGit(null);
      setUsage(null);
      return;
    }
    try {
      const [g, u] = await Promise.all([api.git(), api.usage()]);
      setGit(g);
      setUsage(u);
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

  // Switching workspaces invalidates open editor tabs.
  useEffect(() => {
    setOpenFiles([]);
    setActivePath(null);
  }, [project?.workspacePath]);

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

  const closeFile = useCallback(
    (path: string) => {
      setOpenFiles((prev) => {
        const next = prev.filter((f) => f.path !== path);
        if (activePath === path) {
          setActivePath(next.length > 0 ? next[next.length - 1].path : null);
        }
        return next;
      });
    },
    [activePath],
  );

  const needsWorkspace = page !== "projects" && page !== "agents" && page !== "settings" && !project?.workspacePath;

  return (
    <div className="flex h-screen flex-col bg-surface font-sans text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
      <a
        href="#main"
        className="focusable absolute left-2 top-2 z-50 -translate-y-16 rounded-lg bg-accent px-3 py-1.5 text-sm text-white transition-transform focus:translate-y-0"
      >
        Skip to content
      </a>

      <div className="flex min-h-0 flex-1">
        <ActivityBar page={page} onNavigate={setPage} />
        <ChatPanel hasWorkspace={Boolean(project?.workspacePath)} />

        <main id="main" className="min-w-0 flex-1 overflow-y-auto">
          {!backendUp && (
            <div className="border-b border-rose-200 bg-rose-50 px-8 py-2.5 text-xs text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">
              Backend not reachable at http://localhost:8787 — start it with{" "}
              <code className="font-mono">./scripts/dev.sh</code>
              <button className="focusable ml-3 cursor-pointer rounded underline" onClick={loadProject}>
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
            <>
              {page === "projects" && (
                <ProjectsPage
                  project={project}
                  onProjectChange={loadProject}
                  git={git}
                  onRefreshShell={refreshShell}
                  openFiles={openFiles}
                  activePath={activePath}
                  onOpenFile={openFile}
                  onCloseFile={closeFile}
                  onActivateFile={setActivePath}
                />
              )}
              {page === "agents" && <AgentsPage />}
              {page === "tasks" && <TasksPage />}
              {page === "usage" && <UsagePage />}
              {page === "logs" && <LogsPage />}
              {page === "settings" && <SettingsPage />}
            </>
          )}
        </main>
      </div>

      <StatusBar backendUp={backendUp} project={project} git={git} usage={usage} onNavigate={setPage} />
    </div>
  );
}
