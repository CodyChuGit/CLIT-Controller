/* Shared deterministic display model for the controller tab and Tasks page.
 *
 * The controller is treated like a workflow engine: it produces structured
 * records, and the UI renders those — it must not parse freeform agent prose to
 * decide basic UI state when structured data exists (see
 * docs/task-controller-io-surface.md §Deterministic Display Model).
 *
 * Three separable channels per meaningful result:
 *   - ActionData   strict structured fields, no prose
 *   - HumanSummary fixed, concise shape (≤5 bullets)
 *   - DisplayData  the UI model that drives a card/badge/status
 *
 * This module is the frontend projection layer: it maps the structured records
 * the backend already emits (task events, run/queue/approval lifecycle) into
 * CardModels the shared TimelineCard renders in either density. */

import type { StreamEvent, TaskEvent } from "../types";

/** The fixed card taxonomy shared by both surfaces. */
export type CardType =
  | "TASK_CREATED"
  | "TASK_BRIEF"
  | "STATE_TRANSITION"
  | "QUEUE_ITEM"
  | "RUN_STARTED"
  | "RUN_OUTPUT"
  | "COMMAND_RESULT"
  | "APPROVAL_REQUIRED"
  | "APPROVAL_RESOLVED"
  | "DIFF_SUMMARY"
  | "ARTIFACTS_CHANGED"
  | "QA_STATUS"
  | "FAILURE"
  | "SCHEDULED_OVERFLOW"
  | "FINAL_SUMMARY"
  | "NEEDS_USER";

export type Severity = "info" | "running" | "ok" | "warn" | "error";

/** Strict structured data — no prose. */
export interface ActionData {
  nextAction?: string;
  tool?: string;
  taskId?: string;
  provider?: string;
  step?: string;
  runId?: string;
  queueItemId?: string;
  approvalId?: string;
  stateFrom?: string;
  stateTo?: string;
  artifactIds?: string[];
}

/** Fixed, concise human shape used in cards/timeline/final reports. */
export interface HumanSummary {
  title: string;
  bullets: string[]; // ≤5
}

export interface RawDetailRef {
  label: string;
  /** Inline raw text when already available; otherwise a hint to fetch on open. */
  text?: string;
  kind?: "text" | "stdout" | "stderr" | "log" | "json" | "events" | "directive" | "diff" | "prompt";
}

/** The UI model that drives a card, badge, and status. */
export interface DisplayData {
  cardType: CardType;
  title: string;
  severity: Severity;
  provider?: string | null;
  step?: string | null;
  taskId?: string | null;
  runId?: string | null;
  timestamp?: string | null;
  summary?: HumanSummary;
  artifacts?: string[];
  rawDetail?: RawDetailRef[];
}

export interface CardModel {
  id: string;
  type: CardType;
  display: DisplayData;
  action?: ActionData;
}

/* ----------------------------------------------------- taxonomy presentation */

/** One place that maps a card type to its dot/accent — both surfaces share it so
 *  a TASK_CREATED looks the same compact (dock) and detailed (Tasks). */
export const CARD_STYLE: Record<CardType, { label: string; dot: string; accent: string }> = {
  TASK_CREATED: { label: "Task created", dot: "bg-neutral-400", accent: "border-l-neutral-300 dark:border-l-neutral-600" },
  TASK_BRIEF: { label: "Task brief", dot: "bg-blue-500", accent: "border-l-blue-400" },
  STATE_TRANSITION: { label: "State", dot: "bg-violet-500", accent: "border-l-violet-400" },
  QUEUE_ITEM: { label: "Queued", dot: "bg-neutral-400", accent: "border-l-neutral-300 dark:border-l-neutral-600" },
  RUN_STARTED: { label: "Run started", dot: "bg-blue-500", accent: "border-l-blue-400" },
  RUN_OUTPUT: { label: "Output", dot: "bg-blue-500", accent: "border-l-blue-400" },
  COMMAND_RESULT: { label: "Command", dot: "bg-emerald-500", accent: "border-l-emerald-400" },
  APPROVAL_REQUIRED: { label: "Approval required", dot: "bg-amber-500", accent: "border-l-amber-400" },
  APPROVAL_RESOLVED: { label: "Approval", dot: "bg-emerald-500", accent: "border-l-emerald-400" },
  DIFF_SUMMARY: { label: "Diff", dot: "bg-violet-500", accent: "border-l-violet-400" },
  ARTIFACTS_CHANGED: { label: "Artifacts", dot: "bg-violet-500", accent: "border-l-violet-400" },
  QA_STATUS: { label: "QA", dot: "bg-teal-500", accent: "border-l-teal-400" },
  FAILURE: { label: "Failure", dot: "bg-rose-500", accent: "border-l-rose-500" },
  SCHEDULED_OVERFLOW: { label: "Scheduled", dot: "bg-amber-500", accent: "border-l-amber-400" },
  FINAL_SUMMARY: { label: "Final report", dot: "bg-emerald-500", accent: "border-l-emerald-500" },
  NEEDS_USER: { label: "Needs you", dot: "bg-amber-500", accent: "border-l-amber-500" },
};

export const SEVERITY_TEXT: Record<Severity, string> = {
  info: "text-neutral-500",
  running: "text-blue-600 dark:text-blue-400",
  ok: "text-emerald-600 dark:text-emerald-400",
  warn: "text-amber-600 dark:text-amber-400",
  error: "text-rose-600 dark:text-rose-400",
};

/* --------------------------------------------------------------- projections */

// Map a task.json event type to a card type + severity (structured → UI state).
const TASK_EVENT_MAP: Record<string, { type: CardType; severity: Severity }> = {
  task_created: { type: "TASK_CREATED", severity: "info" },
  step_started: { type: "RUN_STARTED", severity: "running" },
  step_finished: { type: "COMMAND_RESULT", severity: "ok" },
  provider_missing: { type: "FAILURE", severity: "warn" },
  skipped: { type: "STATE_TRANSITION", severity: "warn" },
  blocked: { type: "NEEDS_USER", severity: "warn" },
  local_check: { type: "QA_STATUS", severity: "info" },
  sequence: { type: "STATE_TRANSITION", severity: "info" },
  consult: { type: "STATE_TRANSITION", severity: "info" },
  run: { type: "COMMAND_RESULT", severity: "info" },
  done: { type: "FINAL_SUMMARY", severity: "ok" },
  needs_user: { type: "NEEDS_USER", severity: "warn" },
  queued: { type: "QUEUE_ITEM", severity: "info" },
};

/** Project one durable task event into a CardModel. Structured fields drive the
 *  card; `detail` is the concise human line — raw prose is never re-parsed here. */
export function cardFromTaskEvent(e: TaskEvent, index: number): CardModel {
  const mapped = TASK_EVENT_MAP[e.type] ?? { type: "STATE_TRANSITION" as CardType, severity: "info" as Severity };
  // A finished step that didn't succeed is a FAILURE regardless of the base map.
  let { type, severity } = mapped;
  if (e.type === "step_finished" && e.status && e.status !== "succeeded") {
    type = "FAILURE";
    severity = "error";
  }
  return {
    id: `${e.time}-${index}`,
    type,
    action: { provider: e.provider ?? undefined, step: e.step ?? undefined, stateTo: e.status ?? undefined },
    display: {
      cardType: type,
      title: CARD_STYLE[type].label,
      severity,
      provider: e.provider,
      step: e.step,
      timestamp: e.time,
      summary: { title: CARD_STYLE[type].label, bullets: e.detail ? [e.detail] : [] },
      artifacts: e.artifacts ?? [],
    },
  };
}

// Map a live stream event type to a card type (for the controller transcript).
const STREAM_EVENT_MAP: Record<string, { type: CardType; severity: Severity }> = {
  "task.created": { type: "TASK_CREATED", severity: "info" },
  "task.status_changed": { type: "STATE_TRANSITION", severity: "info" },
  "task.summary_ready": { type: "FINAL_SUMMARY", severity: "ok" },
  "run.started": { type: "RUN_STARTED", severity: "running" },
  "run.finished": { type: "COMMAND_RESULT", severity: "ok" },
  "run.cancelled": { type: "FAILURE", severity: "warn" },
  "command.started": { type: "RUN_STARTED", severity: "running" },
  "command.finished": { type: "COMMAND_RESULT", severity: "ok" },
  "approval.required": { type: "APPROVAL_REQUIRED", severity: "warn" },
  "approval.granted": { type: "APPROVAL_RESOLVED", severity: "ok" },
  "approval.rejected": { type: "APPROVAL_RESOLVED", severity: "warn" },
  "controller.decision_received": { type: "STATE_TRANSITION", severity: "info" },
  "queue.enqueued": { type: "QUEUE_ITEM", severity: "info" },
  "queue.dispatched": { type: "RUN_STARTED", severity: "running" },
  "queue.failed": { type: "FAILURE", severity: "error" },
  "queue.blocked": { type: "NEEDS_USER", severity: "warn" },
  "queue.approval_required": { type: "APPROVAL_REQUIRED", severity: "warn" },
};

/** Project a live event-bus event into a CardModel (compact controller cards). */
export function cardFromStreamEvent(e: StreamEvent): CardModel | null {
  let mapped = STREAM_EVENT_MAP[e.type];
  if (!mapped && e.type.startsWith("queue.")) mapped = { type: "QUEUE_ITEM", severity: "info" };
  if (!mapped) return null;
  const status = typeof e.data?.status === "string" ? (e.data.status as string) : undefined;
  let { type, severity } = mapped;
  if ((e.type === "run.finished" || e.type === "command.finished") && status && status !== "succeeded") {
    type = "FAILURE";
    severity = "error";
  }
  return {
    id: `evt-${e.id}`,
    type,
    action: {
      provider: e.provider ?? undefined,
      step: e.step ?? undefined,
      runId: e.runId ?? undefined,
      queueItemId: e.queueItemId ?? undefined,
      stateTo: status,
    },
    display: {
      cardType: type,
      title: CARD_STYLE[type].label,
      severity,
      provider: e.provider,
      step: e.step,
      runId: e.runId,
      timestamp: e.createdAt,
      summary: { title: CARD_STYLE[type].label, bullets: e.detail ? [e.detail] : [] },
    },
  };
}
