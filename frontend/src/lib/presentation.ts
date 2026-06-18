import type { StreamEvent } from "../types";

/* Presentation records (I/O rebuild, Plane→UI). The UI selects components by a
   deterministic record `kind` derived from the event's validated typed `payload`
   — NOT by sniffing `type` strings or prose. One projection, one taxonomy, used by
   every surface (records/ components render these). */

export type PresentationRecord =
  | { kind: "narrative"; text: string; provider?: string | null }
  | {
      kind: "command";
      command?: string;
      output?: string;
      status?: string;
      exitCode?: number | null;
      durationMs?: number | null;
    }
  | { kind: "approval"; approvalId: string; action: string; reason?: string }
  | { kind: "failure"; title: string; summary?: string }
  | { kind: "summary"; summaryKind: string }
  | { kind: "cancellation"; runId?: string | null };

/** Derive a presentation record from an event's typed payload, or null when the
    event has no semantic payload (transport-only). Deterministic — no prose/regex. */
export function recordFromEvent(e: StreamEvent): PresentationRecord | null {
  const p = e.payload;
  if (!p) return null;
  switch (p.type) {
    case "narrative.delta":
      return { kind: "narrative", text: p.text, provider: e.provider };
    case "narrative.completed":
      return { kind: "narrative", text: p.text ?? "", provider: e.provider };
    case "command.started":
      return { kind: "command", command: p.command, status: "running" };
    case "command.output":
      return { kind: "command", output: p.text };
    case "command.completed":
      return { kind: "command", status: p.status, exitCode: p.exitCode, durationMs: p.durationMs };
    case "approval.requested":
      return { kind: "approval", approvalId: p.approvalId, action: p.action, reason: p.reason };
    case "failure":
      return { kind: "failure", title: p.title, summary: p.summary };
    case "summary.ready":
      return { kind: "summary", summaryKind: p.kind };
    case "cancellation":
      return { kind: "cancellation", runId: p.runId };
    default:
      return null;
  }
}
