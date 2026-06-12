import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import CodeReader from "../components/CodeReader";
import DragHandle from "../components/DragHandle";
import FileTree from "../components/FileTree";
import FileTypeIcon from "../components/FileTypeIcon";
import LogConsole from "../components/LogConsole";
import SourceControlPanel from "../components/SourceControlPanel";
import { loadState, saveState } from "../persist";
import { ChevronDown, ChevronRight, Close, FileIcon, Refresh } from "../components/icons";
import type { CurrentProject, EditorFile, LogsResponse, Tree } from "../types";

interface Props {
  project: CurrentProject | null;
  onProjectChange: () => void;
  openFiles: EditorFile[];
  activePath: string | null;
  onOpenFile: (path: string) => void;
  onOpenDiff: (path: string, staged: boolean) => void;
  onCloseFile: (path: string) => void;
  onActivateFile: (path: string) => void;
}

/** VS Code-style explorer: side panel (workspace, source control, files) + tabbed editor + output panel. */
export default function ProjectsPage({
  project,
  onProjectChange,
  openFiles,
  activePath,
  onOpenFile,
  onOpenDiff,
  onCloseFile,
  onActivateFile,
}: Props) {
  const [pathInput, setPathInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tree, setTree] = useState<Tree | null>(null);
  const [treeExpanded, setTreeExpanded] = useState<Record<string, boolean>>({});
  const [panelW, setPanelW] = useState(() => loadState("explorerW", 288));
  const panelWRef = useRef(panelW);
  const asideRef = useRef<HTMLElement | null>(null);

  const hasWorkspace = Boolean(project?.workspacePath);
  const wsKey = project?.workspacePath ?? "";

  // Folder open/closed state is remembered per workspace.
  useEffect(() => {
    setTreeExpanded(loadState<Record<string, boolean>>(`tree:${wsKey}`, {}));
  }, [wsKey]);

  const toggleDir = (path: string, open: boolean) => {
    setTreeExpanded((prev) => {
      const next = { ...prev, [path]: open };
      saveState(`tree:${wsKey}`, next);
      return next;
    });
  };
  const activeFile = openFiles.find((f) => f.path === activePath) ?? null;

  const refreshTree = useCallback(async () => {
    if (!hasWorkspace) return;
    try {
      setTree(await api.tree());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [hasWorkspace]);

  useEffect(() => {
    setPathInput(project?.workspacePath ?? "");
    setTree(null);
    void refreshTree();
  }, [project?.workspacePath, refreshTree]);

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

  return (
    <div className="flex h-full overflow-hidden">
      {/* ---------- Explorer side panel ---------- */}
      <aside
        ref={asideRef}
        style={{ width: panelW }}
        className="flex shrink-0 flex-col border-r border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900"
      >
        <PanelSection title="Workspace" defaultOpen>
          <div className="space-y-2 px-3 pb-3">
            <input
              className="input font-mono text-xs"
              placeholder="/Users/you/code/my-project"
              value={pathInput}
              onChange={(e) => setPathInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void save()}
              aria-label="Workspace folder path"
            />
            <div className="flex gap-2">
              <button className="btn-primary flex-1 justify-center" onClick={save} disabled={saving || !pathInput.trim()}>
                {saving ? "Saving…" : hasWorkspace ? "Switch" : "Open"}
              </button>
              {hasWorkspace && (
                <button className="btn-secondary" onClick={() => void api.openWorkspaceFolder()}>
                  Finder
                </button>
              )}
            </div>
            <p className="text-[11px] leading-snug text-neutral-500 dark:text-neutral-400">
              Paths are resolved by the local Python backend; saving creates{" "}
              <code className="font-mono">.agentflow/</code>.
            </p>
            {error && (
              <p className="text-xs text-rose-600 dark:text-rose-400" role="alert">
                {error}
              </p>
            )}
          </div>
        </PanelSection>

        {hasWorkspace && project?.workspacePath && (
          <SourceControlPanel workspacePath={project.workspacePath} onOpenDiff={onOpenDiff} />
        )}

        {hasWorkspace && (
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex items-center justify-between px-3 py-1.5">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                Files{tree ? ` (${tree.fileCount})` : ""}
              </span>
              <IconButton label="Refresh file tree" onClick={() => void refreshTree()}>
                <Refresh className="h-3.5 w-3.5" />
              </IconButton>
            </div>
            <div className="min-h-0 flex-1 overflow-auto">
              {tree ? (
                <FileTree
                  nodes={tree.children}
                  onOpenFile={onOpenFile}
                  selected={activePath}
                  truncated={tree.truncated}
                  expanded={treeExpanded}
                  onToggleDir={toggleDir}
                />
              ) : (
                <div className="space-y-2 p-3" aria-hidden="true">
                  {[0, 1, 2, 3, 4].map((i) => (
                    <div key={i} className="skeleton h-4" style={{ width: `${85 - i * 9}%` }} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </aside>

      <DragHandle
        orientation="vertical"
        label="Resize explorer panel"
        onMove={(x) => {
          const left = asideRef.current?.getBoundingClientRect().left ?? 0;
          const w = Math.min(520, Math.max(200, x - left));
          panelWRef.current = w;
          setPanelW(w);
        }}
        onDone={() => saveState("explorerW", panelWRef.current)}
      />

      {/* ---------- Editor + output ---------- */}
      <section className="flex min-w-0 flex-1 flex-col">
        {openFiles.length > 0 && (
          <div
            className="flex h-8 shrink-0 items-stretch overflow-x-auto border-b border-neutral-200 bg-surface dark:border-neutral-800 dark:bg-neutral-950"
            role="tablist"
            aria-label="Open files"
          >
            {openFiles.map((f) => {
              const active = f.path === activePath;
              const name = f.path.split("/").pop() ?? f.path;
              return (
                <div
                  key={f.path}
                  className={`relative flex shrink-0 items-center border-r border-neutral-200 transition-colors duration-150 dark:border-neutral-800 ${
                    active
                      ? "bg-white dark:bg-neutral-900"
                      : "hover:bg-neutral-100 dark:hover:bg-neutral-800/60"
                  }`}
                >
                  {active && <span className="absolute inset-x-0 top-0 h-0.5 bg-accent" aria-hidden="true" />}
                  <button
                    role="tab"
                    aria-selected={active}
                    title={f.path}
                    onClick={() => onActivateFile(f.path)}
                    className={`focusable flex cursor-pointer items-center gap-1.5 py-1.5 pl-2.5 pr-1 font-mono text-[11px] ${
                      active ? "text-neutral-800 dark:text-neutral-100" : "text-neutral-500 dark:text-neutral-400"
                    }`}
                  >
                    <FileTypeIcon name={name} className="shrink-0" />
                    {name}
                    {f.error && <span className="text-rose-500">!</span>}
                  </button>
                  <IconButton label={`Close ${name}`} onClick={() => onCloseFile(f.path)}>
                    <Close className="h-3 w-3" />
                  </IconButton>
                </div>
              );
            })}
          </div>
        )}

        <div className="min-h-0 flex-1">
          {hasWorkspace ? (
            <CodeReader file={activeFile} />
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-2 bg-white text-center dark:bg-neutral-900">
              <FileIcon className="h-7 w-7 text-neutral-300 dark:text-neutral-600" />
              <p className="text-sm text-neutral-500">Open a workspace folder to browse and read its files.</p>
            </div>
          )}
        </div>

        <OutputPanel />
      </section>
    </div>
  );
}

/* ---------- helpers ---------- */

function IconButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      className="icon-btn mx-1"
    >
      {children}
    </button>
  );
}

function PanelSection({
  title,
  badge,
  action,
  defaultOpen = false,
  children,
}: {
  title: string;
  badge?: React.ReactNode;
  action?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const storageKey = `section:${title}`;
  const [open, setOpenState] = useState(() => loadState(storageKey, defaultOpen));
  const setOpen = (next: boolean) => {
    setOpenState(next);
    saveState(storageKey, next);
  };
  return (
    <div className="shrink-0 border-b border-neutral-200 dark:border-neutral-800">
      <div className="flex items-center">
        <button
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          className="focusable flex flex-1 cursor-pointer items-center gap-1 px-2 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide text-neutral-500 transition-colors hover:text-neutral-800 dark:hover:text-neutral-200"
        >
          {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          {title}
          {badge && <span className="ml-1">{badge}</span>}
        </button>
        {action}
      </div>
      {open && children}
    </div>
  );
}

function OutputPanel() {
  const [open, setOpenState] = useState(() => loadState("outputOpen", true));
  const setOpen = (next: boolean) => {
    setOpenState(next);
    saveState("outputOpen", next);
  };
  const [height, setHeight] = useState(() => loadState("outputH", 160));
  const heightRef = useRef(height);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const [data, setData] = useState<LogsResponse | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.logs());
    } catch {
      /* backend banner handles outages */
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    void load();
    const id = window.setInterval(load, 5000);
    return () => window.clearInterval(id);
  }, [open, load]);

  return (
    <div className="shrink-0 border-t border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
      {open && (
        <DragHandle
          orientation="horizontal"
          label="Resize output panel"
          onMove={(_, y) => {
            const bottom = bodyRef.current?.getBoundingClientRect().bottom ?? window.innerHeight;
            const h = Math.min(480, Math.max(80, bottom - y));
            heightRef.current = h;
            setHeight(h);
          }}
          onDone={() => saveState("outputH", heightRef.current)}
        />
      )}
      <div className="flex h-8 items-center gap-2 px-3">
        <button
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          className="focusable flex cursor-pointer items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-neutral-500 transition-colors hover:text-neutral-800 dark:hover:text-neutral-200"
        >
          {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          Output · Logs
        </button>
        {data && data.running.length > 0 && (
          <span className="rounded-full bg-blue-100 px-1.5 text-[10px] font-medium tabular-nums text-blue-700 dark:bg-blue-950 dark:text-blue-300">
            {data.running.length} running
          </span>
        )}
        <span className="flex-1" />
        {open && (
          <>
            <IconButton label="Refresh logs" onClick={() => void load()}>
              <Refresh className="h-3.5 w-3.5" />
            </IconButton>
            <IconButton
              label="Clear log view"
              onClick={() => void api.clearLogView().then(load)}
            >
              <Close className="h-3.5 w-3.5" />
            </IconButton>
          </>
        )}
      </div>
      {open && (
        <div ref={bodyRef} style={{ height }} className="overflow-auto border-t border-neutral-100 px-3 dark:border-neutral-800">
          <LogConsole entries={data?.entries ?? []} running={data?.running ?? []} />
        </div>
      )}
    </div>
  );
}
