/* Frontend mirror of the typed I/O contracts (I/O rebuild, Phase 1).

   These are the runtime-validated, versioned shapes for the input plane
   (InputSubmission — what the UI sends) and the operational-event plane
   (OutputEvent envelope + discriminated payload — what the UI receives). They
   mirror backend/agentflow/io_contracts.py. Validators are hand-written guards
   (consistent with lib/streamEvent.ts) so there is no new dependency; they never
   throw and reject unsupported schema versions, so malformed/foreign data fails
   safely instead of corrupting UI state. */

export const IO_SCHEMA_VERSION = "1";

// ---------------------------------------------------------------- input plane

export type InputReference =
  | { kind: "file"; path: string }
  | { kind: "folder"; path: string }
  | { kind: "diff"; path: string; staged?: boolean }
  | { kind: "task_artifact"; taskId: string; name: string }
  | { kind: "run"; runId: string }
  | { kind: "event_range"; fromEventId: number; toEventId: number };

export type InputDestination =
  | { kind: "controller" }
  | { kind: "provider"; provider: string }
  | {
      kind: "task";
      taskId: string;
      intent: "continue" | "clarify" | "retry" | "fix" | "reroute" | "ask";
    };

export type SubmitMode = "message" | "create_task" | "continue" | "retry" | "reroute";

export interface InputSubmission {
  schemaVersion: "1";
  id: string;
  workspaceId: string;
  destination: InputDestination;
  content: { text: string; references: InputReference[] };
  context: { taskId?: string; step?: string; provider?: string; orchestrationMode?: string };
  behavior: { submitMode: SubmitMode };
  createdAt: string;
}

/** Build a well-formed submission; the single way the UI expresses intent + destination. */
export function buildSubmission(args: {
  id: string;
  workspaceId: string;
  destination: InputDestination;
  text: string;
  references?: InputReference[];
  context?: InputSubmission["context"];
  submitMode?: SubmitMode;
  createdAt: string;
}): InputSubmission {
  return {
    schemaVersion: IO_SCHEMA_VERSION,
    id: args.id,
    workspaceId: args.workspaceId,
    destination: args.destination,
    content: { text: args.text, references: args.references ?? [] },
    context: args.context ?? {},
    behavior: { submitMode: args.submitMode ?? "message" },
    createdAt: args.createdAt,
  };
}

export function validateSubmission(raw: unknown): InputSubmission | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (r.schemaVersion !== IO_SCHEMA_VERSION) return null; // unsupported version → fail safe
  const dest = r.destination as Record<string, unknown> | undefined;
  const content = r.content as Record<string, unknown> | undefined;
  if (!dest || typeof dest.kind !== "string") return null;
  if (!content || typeof content.text !== "string" || content.text.length === 0) return null;
  if (typeof r.id !== "string" || typeof r.workspaceId !== "string") return null;
  return raw as InputSubmission;
}

// ----------------------------------------------------- operational-event plane

export type EventPayload =
  | { type: "narrative.delta"; text: string }
  | { type: "narrative.completed"; text?: string }
  | { type: "command.started"; command: string }
  | { type: "command.output"; text: string }
  | { type: "command.completed"; exitCode?: number; durationMs?: number; status?: string }
  | { type: "task.state"; taskId: string; state: string }
  | { type: "queue.state"; activeCount?: number }
  | { type: "approval.requested"; approvalId: string; action: string; reason?: string }
  | { type: "approval.resolved"; approvalId: string; approved: boolean }
  | { type: "failure"; title: string; summary?: string }
  | { type: "cancellation"; runId?: string }
  | { type: "summary.ready"; kind: string };

const PAYLOAD_TYPES = new Set<string>([
  "narrative.delta",
  "narrative.completed",
  "command.started",
  "command.output",
  "command.completed",
  "task.state",
  "queue.state",
  "approval.requested",
  "approval.resolved",
  "failure",
  "cancellation",
  "summary.ready",
]);

export interface OutputEventEnvelope {
  schemaVersion: "1";
  id: string;
  workspaceId: string;
  createdAt: string;
  taskId?: string;
  runId?: string;
  channel?: "assistant" | "controller" | "stdout" | "stderr" | "system";
  sequence?: number;
  redacted: boolean;
  truncated: boolean;
  payload: EventPayload;
}

/** Validate a typed OutputEvent envelope; null on unsupported version or unknown
    payload type (fail-safe). */
export function validateOutputEvent(raw: unknown): OutputEventEnvelope | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (r.schemaVersion !== IO_SCHEMA_VERSION) return null;
  if (typeof r.id !== "string" || typeof r.workspaceId !== "string") return null;
  const p = r.payload as Record<string, unknown> | undefined;
  if (!p || typeof p.type !== "string" || !PAYLOAD_TYPES.has(p.type)) return null;
  return raw as OutputEventEnvelope;
}
