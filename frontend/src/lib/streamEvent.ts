import { validatePayload } from "./ioContracts";
import type { StreamEvent } from "../types";

/* Pillar 5 / P2-14 — validate frames crossing the network trust boundary.
   SSE and polling deliver arbitrary JSON; the store must not ingest malformed
   frames blindly. The only load-bearing fields for the store are `id` (number)
   and `type` (string); everything else is normalized to its declared shape.
   Returns null for a frame missing the essentials so callers can drop it. */
export function coerceStreamEvent(raw: unknown): StreamEvent | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (typeof r.id !== "number" || typeof r.type !== "string") return null;

  const str = (v: unknown): string | null => (typeof v === "string" ? v : null);
  return {
    id: r.id,
    type: r.type,
    createdAt: str(r.createdAt) ?? "",
    time: str(r.time) ?? str(r.createdAt) ?? "",
    workspacePath: str(r.workspacePath),
    provider: str(r.provider),
    taskId: str(r.taskId),
    runId: str(r.runId),
    queueItemId: str(r.queueItemId),
    step: str(r.step),
    sequence: typeof r.sequence === "number" ? r.sequence : null,
    channel: str(r.channel),
    textDelta: str(r.textDelta),
    redacted: r.redacted === true,
    truncated: r.truncated === true,
    detail: str(r.detail) ?? "",
    data: r.data && typeof r.data === "object" ? (r.data as Record<string, unknown>) : {},
    payload: validatePayload(r.payload), // typed Plane-2 payload, validated (null if absent/unknown)
  };
}
