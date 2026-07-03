import type { InputSubmission } from "./lib/ioContracts";
import type {
  Approval,
  ChatSendResult,
  ChatState,
  CurrentProject,
  ContextReport,
  EventsResponse,
  Exchange,
  FileContent,
  FileDiff,
  GitInfo,
  GitStatus,
  InstallResult,
  LiveProviderUsage,
  LoginResult,
  LogsResponse,
  PreviewState,
  QueueState,
  RunRecord,
  OrchestrationMode,
  Provider,
  Recommendation,
  RoutingConfig,
  RunStepResult,
  Settings,
  TaskDetail,
  TaskMeta,
  TerminalDiagnostics,
  Tree,
  Usage,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? "{}" : JSON.stringify(body) });

export const api = {
  health: () => get<{ ok: boolean }>("/health"),

  // projects
  current: () => get<CurrentProject>("/projects/current"),
  setWorkspace: (path: string) =>
    post<{ ok: boolean; workspacePath: string }>("/projects/workspace", { path }),
  tree: () => get<Tree>("/projects/tree"),
  file: (path: string) => get<FileContent>(`/projects/file?path=${encodeURIComponent(path)}`),
  saveFile: (path: string, content: string) =>
    post<FileContent>("/projects/file", { path, content }),
  git: () => get<GitInfo>("/projects/git"),
  gitStatus: () => get<GitStatus>("/projects/git/status"),
  gitFileDiff: (path: string, staged: boolean) =>
    get<FileDiff>(`/projects/git/file-diff?path=${encodeURIComponent(path)}&staged=${staged}`),
  gitStage: (path: string | null) =>
    post<{ ok: boolean; output: string }>("/projects/git/stage", { path }),
  gitUnstage: (path: string) =>
    post<{ ok: boolean; output: string }>("/projects/git/unstage", { path }),
  gitCommit: (message: string) =>
    post<{ ok: boolean; output: string }>("/projects/git/commit", { message }),
  openWorkspaceFolder: () => post<{ ok: boolean }>("/projects/open-folder"),
  settings: () => get<Settings>("/projects/settings"),
  saveSettings: (body: {
    routing?: RoutingConfig;
    commandTemplates?: Record<string, string>;
    headroom?: { enabled?: boolean; minChars?: number };
    ponytail?: { level: string };
  }) => post<Settings>("/projects/settings", body),

  // context intelligence
  contextPreview: (task: string, maxTokens?: number) =>
    post<ContextReport>(
      "/context/preview",
      maxTokens === undefined ? { task } : { task, maxTokens },
    ),
  contextReport: (id: string) => get<ContextReport>(`/context/reports/${encodeURIComponent(id)}`),

  // agents
  agents: () => get<Provider[]>("/agents"),
  checkAgent: (id: string) => post<Provider>("/agents/check", { id }),
  checkAllAgents: () => post<Provider[]>("/agents/check-all"),
  loginAgent: (id: string) => post<LoginResult>("/agents/login", { id }),
  installAgent: (id: string) => post<InstallResult>("/agents/install", { id }),
  setAgentModel: (id: string, model: string) =>
    post<{ ok: boolean; id: string; model: string | null }>("/agents/model", { id, model }),

  // tasks
  tasks: () => get<TaskMeta[]>("/tasks"),
  createTask: (title: string, goal: string) => post<TaskMeta>("/tasks", { title, goal }),
  task: (id: string) => get<TaskDetail>(`/tasks/${encodeURIComponent(id)}`),
  runStep: (taskId: string, step: string, confirm = false) =>
    post<RunStepResult>(`/tasks/${encodeURIComponent(taskId)}/run/${step}`, { confirm }),
  runFull: (taskId: string, confirm = false) =>
    post<RunStepResult>(`/tasks/${encodeURIComponent(taskId)}/run-full`, { confirm }),
  stop: (runId?: string) => post<{ stopped: string[] }>("/tasks/stop", { runId: runId ?? null }),
  openTaskFolder: (taskId: string) =>
    post<{ ok: boolean }>(`/tasks/${encodeURIComponent(taskId)}/open-folder`),
  taskLogs: (taskId: string) =>
    get<{ files: { name: string; size: number; content: string }[]; runs: TaskDetail["runs"] }>(
      `/tasks/${encodeURIComponent(taskId)}/logs`,
    ),
  taskFile: (taskId: string, name: string) =>
    get<{ name: string; content: string }>(
      `/tasks/${encodeURIComponent(taskId)}/file?name=${encodeURIComponent(name)}`,
    ),

  // usage
  usage: () => get<Usage>("/usage"),
  setMode: (mode: OrchestrationMode) => post<Usage>("/usage/mode", { mode }),
  setProviderHealth: (provider: string, health: string) =>
    post<Usage>("/usage/provider-health", { provider, health }),
  usageLive: (force = false) =>
    get<Record<string, LiveProviderUsage>>(`/usage/live?force=${force}`),
  recommendations: () => get<Recommendation>("/usage/recommendations"),

  // logs
  logs: () => get<LogsResponse>("/logs"),
  clearLogView: () => post<{ ok: boolean }>("/logs/clear-view"),

  // terminals (live PTY sessions are over WebSocket; these are control/metadata)
  terminalDiagnostics: (provider: string) =>
    get<TerminalDiagnostics>(`/terminals/${encodeURIComponent(provider)}/diagnostics`),
  terminalKill: (provider: string) =>
    post<{ ok: boolean }>(`/terminals/${encodeURIComponent(provider)}/kill`),

  // queue
  queue: () => get<QueueState>("/queue"),
  queueAdd: (taskId: string, steps: string[]) => post<QueueState>("/queue/add", { taskId, steps }),
  queueApprove: (itemId: string) =>
    post<{ status: string; message?: string; queue: QueueState }>("/queue/approve", { itemId }),
  queueRemove: (itemId: string) => post<QueueState>("/queue/remove", { itemId }),
  queueClear: () => post<QueueState>("/queue/clear"),
  queueRetry: (itemId: string) =>
    post<{ status: string; message?: string } & QueueState>("/queue/retry", { itemId }),
  queueSkip: (itemId: string) =>
    post<{ status: string; message?: string } & QueueState>("/queue/skip", { itemId }),
  queueReroute: (itemId: string, provider: string) =>
    post<{ status: string; message?: string } & QueueState>("/queue/reroute", { itemId, provider }),

  // durable state (events ledger, run ledger, approvals)
  events: (cursor = 0) => get<EventsResponse>(`/events?cursor=${cursor}`),
  run: (id: string) => get<RunRecord>(`/runs/${id}`),
  approvals: (pendingOnly = false) =>
    get<{ approvals: Approval[] }>(`/approvals?pendingOnly=${pendingOnly}`),
  approvalApprove: (id: string) =>
    post<{ status: string; approval: Approval }>(`/approvals/${id}/approve`),
  approvalReject: (id: string) =>
    post<{ status: string; approval: Approval }>(`/approvals/${id}/reject`),

  // preview
  preview: () => get<PreviewState>("/preview"),
  previewCheck: () => get<{ ok: boolean }>("/preview/check"),
  previewSetUrl: (url: string) => post<PreviewState>("/preview/url", { url }),
  previewStart: (command?: string) =>
    post<PreviewState & { status?: string; message?: string }>("/preview/start", { command }),
  previewStop: () => post<PreviewState & { stopped: boolean }>("/preview/stop"),

  taskExchanges: (id: string) =>
    get<{ steps: Record<string, Exchange[]> }>(`/tasks/${encodeURIComponent(id)}/exchanges`),

  // chat
  chat: () => get<ChatState>("/chat"),
  chatSend: (message: string, provider: string | null) =>
    post<ChatSendResult>("/chat/send", { message, provider: provider ?? undefined }),
  chatDirect: (provider: string, message: string) =>
    post<ChatSendResult>("/chat/direct", { message, provider }),
  // Typed input plane (I/O rebuild): destination + intent are explicit fields.
  chatSubmit: (submission: InputSubmission) => post<ChatSendResult>("/chat/submit", submission),
  chatStop: (channel: string) => post<{ stopped: boolean }>("/chat/stop", { channel }),
  chatClear: (channel: string) => post<{ ok: boolean }>("/chat/clear", { channel }),
};
