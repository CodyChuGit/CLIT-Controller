export type Health = "green" | "yellow" | "red";
export type OrchestrationMode = "maximum_quality" | "balanced" | "budget_saver" | "manual_approval";

export interface CurrentProject {
  workspacePath: string | null;
  name?: string;
  agentflowDir?: string;
  routing?: RoutingConfig;
}

export interface RoutingConfig {
  orchestrator: string;
  pm: string;
  engineer: string;
  qa: string;
}

export interface Provider {
  id: string;
  displayName: string;
  role: string;
  executableNames: string[];
  installed: boolean;
  executablePath: string | null;
  version: string | null;
  status: string;
  authMode: string;
  usageMode: string;
  usageHealth: Health | null;
  callsToday: number;
  manualBudgetLevel: string | null;
  preferredUse: string;
  lastChecked: string | null;
  lastLog: string;
  installHint: string;
  installCommand: string | null;
  installing: boolean;
  loginCommand: string | null;
  versionCommand: string;
  statusCommand: string | null;
  model: string;
  modelEditable: boolean;
  modelOptions: string[];
}

export interface InstallResult {
  status: string;
  message?: string;
  runId?: string;
  command?: string;
}

export interface TreeNode {
  name: string;
  path: string;
  type: "dir" | "file";
  size?: number;
  previewable?: boolean;
  children?: TreeNode[];
}

export interface Tree {
  root: string;
  children: TreeNode[];
  fileCount: number;
  truncated: boolean;
}

export interface FileContent {
  path: string;
  size: number;
  truncated: boolean;
  content: string;
}

/** A file open in the editor (content null while errored). */
export interface EditorFile {
  path: string;
  content: string | null;
  size?: number;
  truncated?: boolean;
  error?: string;
  kind?: "file" | "diff";
}

export interface GitFileEntry {
  path: string;
  code: string; // M / A / D / R / U …
}

export interface GitStatus {
  installed: boolean;
  isRepo: boolean;
  branch?: string | null;
  upstream?: string | null;
  ahead?: number;
  behind?: number;
  staged?: GitFileEntry[];
  changes?: GitFileEntry[];
}

export interface FileDiff {
  path: string;
  staged: boolean;
  diff: string;
  truncated: boolean;
}

export interface GitInfo {
  installed: boolean;
  isRepo: boolean;
  branch?: string;
  statusShort?: string;
  diffStat?: string;
  changedFiles?: string[];
  changedFileCount?: number;
  error?: string;
}

export interface StepState {
  status: string;
  provider?: string;
  runId?: string;
  exitCode?: number | null;
  updatedAt?: string;
  artifactsWritten?: string[];
  codeChanged?: string[];
  promptFile?: string;
  logFile?: string;
}

export interface TaskEvent {
  time: string;
  type: string;
  step: string | null;
  provider: string | null;
  detail: string;
  artifacts?: string[];
  codeChanged?: string[];
  status?: string;
}

export interface TaskMeta {
  id: string;
  title: string;
  goal: string;
  createdAt: string;
  status: string;
  steps: Record<string, StepState>;
  fullSequence: { status: string; currentStep: string | null };
  events?: TaskEvent[];
  orchestrated?: boolean;
  consults?: number;
}

export interface StepPreview {
  step: string;
  label: string;
  provider: string;
  providerInstalled: boolean;
  commandPreview: string;
  promptChars: number;
  reads: string[];
  writes: string[];
}

export interface RunInfo {
  id: string;
  taskId: string | null;
  step: string | null;
  provider: string | null;
  status: string;
  exitCode: number | null;
  startedAt: string;
  endedAt: string | null;
  durationMs: number | null;
  commandPreview: string;
  cwd: string;
  stdout: string;
  stderr: string;
  logFile: string | null;
  failureKind?: string | null;
}

export interface Recommendation {
  mode: OrchestrationMode;
  modeLabel: string;
  budgetContext: string;
  lines: string[];
  warnings: string[];
  selectedProvider: string;
  manualApprovalRecommended: boolean;
  cheaperRouteRecommended: boolean;
  health: Record<string, Health>;
}

export interface TaskDetail {
  task: TaskMeta;
  taskDir: string;
  files: { name: string; size: number; modifiedAt: string }[];
  runs: RunInfo[];
  stepPreviews: Record<string, StepPreview>;
  recommendation: Recommendation;
}

export interface RunStepResult extends Partial<StepPreview> {
  status: string;
  runId?: string;
  warning?: string;
  message?: string;
  savedPromptTo?: string;
  previews?: StepPreview[];
}

export interface ProviderUsage {
  limitCalls: number | null;
  windowHours: number;
  windowStartedAt: string | null;
  callsToday: number;
  manualBudgetLevel: string;
  health: Health;
  preferredUse: string;
  estimatedPromptChars: number;
  estimatedOutputChars: number;
  lastCommandDuration: number;
  lastStatus: string;
}

export interface LiveWindow {
  label: string;
  usedPercent: number;
  resetsAt: number | null;
  resetsText?: string | null;
}

export interface LiveProviderUsage {
  available: boolean;
  plan?: string;
  windows?: LiveWindow[];
  sourcedAt?: string;
  note?: string;
}

export interface Usage {
  mode: string;
  orchestrationMode: OrchestrationMode;
  providers: Record<string, ProviderUsage>;
  expensiveCallsAvoided: number;
  localStepsCompleted: number;
}

export interface LogEntry {
  id: string;
  time: string;
  source: string;
  provider: string | null;
  taskId: string | null;
  step: string | null;
  status: string;
  summary: string;
  output: string;
}

export interface LogsResponse {
  entries: LogEntry[];
  running: RunInfo[];
}

/** Metadata for the live Terminals tab; the sessions themselves stream over
 *  WebSocket. `installed` says whether each CLI was found on PATH. */
export interface TerminalsStatus {
  providers: string[];
  installed: Record<string, boolean>;
}

export interface Settings {
  routing: RoutingConfig;
  commandTemplates: Record<string, string>;
  models: Record<string, string>;
  workspacePath: string | null;
  globalConfigPath: string;
  workspaceConfigPath: string | null;
  usageFilePath: string | null;
}

export interface LoginResult {
  launched: boolean;
  command: string | null;
  message: string;
}

/** One archived prompt → output pair for a step, rebuilt from the task's logs dir. */
export interface Exchange {
  stamp: string;
  prompt: string;
  output: string;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  time: string;
  provider?: string;
  durationMs?: number;
}

export interface ChatPending {
  runId: string;
  status: string;
  outputTail: string;
}

export interface ChatState {
  messages: ChatMessage[];
  pending: ChatPending | null;
  /** Direct chat history per agent provider, outside the traffic-control loop. */
  channels: Record<string, ChatMessage[]>;
  channelPending: Record<string, ChatPending | null>;
  defaultProvider: string;
  providers: { id: string; installed: boolean }[];
}

export interface ChatSendResult {
  status: string;
  message?: string;
  runId?: string;
  provider?: string;
}

export interface QueueItem {
  id: string;
  taskId: string;
  step: string;
  label: string;
  provider: string;
  status: string; // queued | awaiting_approval | blocked | running | done | failed | skipped | cancelled
  source: string;
  enqueuedAt: string;
  startedAt?: string;
  finishedAt?: string;
  note: string | null;
  runId: string | null;
  attempt?: number;
  providerOverride?: string | null;
}

export interface AgentflowEvent {
  id: number;
  time: string;
  type: string;
  taskId: string | null;
  step: string | null;
  provider: string | null;
  detail: string;
  data: Record<string, unknown>;
}

export interface EventsResponse {
  events: AgentflowEvent[];
  cursor: number;
}

/** One live event from the workspace event bus (SSE `/api/events/stream` or the
 *  `/api/events` polling fallback). Text deltas stream progressively. */
export interface StreamEvent {
  id: number;
  type: string;
  createdAt: string;
  time: string;
  workspacePath: string | null;
  provider: string | null;
  taskId: string | null;
  runId: string | null;
  queueItemId: string | null;
  step: string | null;
  sequence: number | null;
  channel: string | null;
  textDelta: string | null;
  redacted: boolean;
  truncated: boolean;
  detail: string;
  data: Record<string, unknown>;
}

/** Accumulated, progressively-growing output for one run, assembled from deltas. */
export interface RunStream {
  runId: string;
  provider: string | null;
  taskId: string | null;
  step: string | null;
  kind: "run" | "command" | "chat" | "controller";
  stdout: string;
  stderr: string;
  status: "running" | "finished" | "cancelled";
  updatedAt: number;
}

export type StreamConnection = "live" | "polling" | "off";

export interface RunRecord {
  id: string;
  workspacePath: string;
  commandPreview: string;
  cwd: string;
  provider: string | null;
  taskId: string | null;
  step: string | null;
  status: string;
  pid: number | null;
  startedAt: string;
  endedAt: string | null;
  durationMs: number | null;
  exitCode: number | null;
  promptFile: string | null;
  logFile: string | null;
  stdoutTail: string;
  stderrTail: string;
  outputTruncated: boolean;
  failureKind: string | null;
}

export interface Approval {
  id: string;
  action: string;
  kind: string;
  source: string;
  provider: string | null;
  taskId: string | null;
  reason: string;
  status: string; // pending | approved | rejected
  createdAt: string;
  resolvedAt: string | null;
  resolver: string | null;
}

export interface PreviewState {
  running: boolean;
  runId: string | null;
  command: string;
  url: string;
  output: string;
  status: string | null;
  exitCode: number | null;
}

export interface QueueState {
  items: QueueItem[];
  mode: string;
  activeCount: number;
  runningProviders: string[];
}
