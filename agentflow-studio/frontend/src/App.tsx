import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import Sidebar, { type PageId } from "./components/Sidebar";
import AgentsPage from "./pages/AgentsPage";
import LogsPage from "./pages/LogsPage";
import ProjectsPage from "./pages/ProjectsPage";
import SettingsPage from "./pages/SettingsPage";
import TasksPage from "./pages/TasksPage";
import UsagePage from "./pages/UsagePage";
import type { CurrentProject } from "./types";

export default function App() {
  const [page, setPage] = useState<PageId>("projects");
  const [project, setProject] = useState<CurrentProject | null>(null);
  const [backendUp, setBackendUp] = useState(true);

  const loadProject = useCallback(async () => {
    try {
      await api.health();
      setBackendUp(true);
      setProject(await api.current());
    } catch {
      setBackendUp(false);
    }
  }, []);

  useEffect(() => {
    void loadProject();
  }, [loadProject]);

  const needsWorkspace = page !== "projects" && page !== "agents" && page !== "settings" && !project?.workspacePath;

  return (
    <div className="flex h-screen bg-surface font-sans text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
      <a
        href="#main"
        className="focusable absolute left-2 top-2 z-50 -translate-y-16 rounded-lg bg-accent px-3 py-1.5 text-sm text-white transition-transform focus:translate-y-0"
      >
        Skip to content
      </a>
      <Sidebar page={page} onNavigate={setPage} project={project} backendUp={backendUp} />

      <main id="main" className="min-w-0 flex-1 overflow-y-auto">
        {!backendUp && (
          <div className="border-b border-rose-200 bg-rose-50 px-8 py-2.5 text-xs text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">
            Backend not reachable at http://localhost:8787 — start it with <code className="font-mono">./scripts/dev.sh</code>
            <button className="ml-3 underline" onClick={loadProject}>Retry</button>
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
            {page === "projects" && <ProjectsPage project={project} onProjectChange={loadProject} />}
            {page === "agents" && <AgentsPage />}
            {page === "tasks" && <TasksPage />}
            {page === "usage" && <UsagePage />}
            {page === "logs" && <LogsPage />}
            {page === "settings" && <SettingsPage />}
          </>
        )}
      </main>
    </div>
  );
}
