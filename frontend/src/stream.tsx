import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { coerceStreamEvent } from "./lib/streamEvent";
import type { RunStream, StreamConnection, StreamEvent } from "./types";

/* One workspace-scoped event subscription for the whole app.

   The backend owns streaming (redaction, ordering, durability). This module keeps
   a single SSE connection (with a polling fallback), dedupes by event id, resumes
   from a cursor, and accumulates per-run text deltas into a small external store
   that surfaces (Agent Dock, Tasks, Logs, footer) read via hooks. Rapid deltas are
   coalesced for render with one rAF flush — never batched so much that the user
   waits for the full output. See docs/text-streaming-across-the-board.md. */

const STDOUT_CAP = 300_000; // keep the tail; full output lives in the run log on disk
const RECENT_CAP = 250;
const POLL_MS = 1500;

const isDelta = (t: string) =>
  t === "run.output" || t === "run.stderr" || t === "chat.delta" || t === "controller.delta";

function cap(s: string): string {
  return s.length > STDOUT_CAP ? s.slice(-STDOUT_CAP) : s;
}

function kindFromType(t: string): RunStream["kind"] {
  if (t.startsWith("chat.")) return "chat";
  if (t.startsWith("controller.")) return "controller";
  if (t.startsWith("command.")) return "command";
  return "run";
}

class StreamStore {
  cursor = 0;
  connection: StreamConnection = "off";
  structuralRev = 0;
  recent: StreamEvent[] = [];
  private runs = new Map<string, RunStream>();
  private listeners = new Set<() => void>();
  private flushQueued = false;

  subscribe = (cb: () => void): (() => void) => {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  };

  // Coalesce notifications: at most one flush per animation frame.
  private notify(): void {
    if (this.flushQueued) return;
    this.flushQueued = true;
    const flush = () => {
      this.flushQueued = false;
      this.listeners.forEach((l) => l());
    };
    if (typeof requestAnimationFrame !== "undefined") requestAnimationFrame(flush);
    else setTimeout(flush, 16);
  }

  reset(): void {
    this.cursor = 0;
    this.connection = "off";
    this.structuralRev = 0;
    this.recent = [];
    this.runs = new Map();
    this.notify();
  }

  setConnection(c: StreamConnection): void {
    if (this.connection !== c) {
      this.connection = c;
      this.notify();
    }
  }

  getConnection = (): StreamConnection => this.connection;
  getStructuralRev = (): number => this.structuralRev;
  getRecent = (): StreamEvent[] => this.recent;
  getRun = (runId: string | null | undefined): RunStream | undefined =>
    runId ? this.runs.get(runId) : undefined;

  apply(e: StreamEvent): void {
    if (!e || typeof e.id !== "number" || e.id <= this.cursor) return; // dedupe by id / resume
    this.cursor = e.id;
    const t = e.type;
    if (t === "run.heartbeat") return; // liveness only; SSE/cursor already advanced
    if (isDelta(t)) {
      this.applyDelta(e);
    } else if (t === "run.started" || t === "command.started") {
      this.touchRun(e, "running");
      this.structural(e);
    } else if (
      t === "run.finished" ||
      t === "chat.finished" ||
      t === "command.finished" ||
      t === "run.cancelled"
    ) {
      this.touchRun(e, t === "run.cancelled" ? "cancelled" : "finished");
      this.structural(e);
    } else {
      this.structural(e); // queue.* / task.* / approval.* / controller.decision_received / …
    }
    this.notify();
  }

  private blankRun(e: StreamEvent, status: RunStream["status"]): RunStream {
    return {
      runId: e.runId as string,
      provider: e.provider,
      taskId: e.taskId,
      step: e.step,
      kind: kindFromType(e.type),
      stdout: "",
      stderr: "",
      status,
      updatedAt: 0,
    };
  }

  private applyDelta(e: StreamEvent): void {
    if (!e.runId || !e.textDelta) return;
    const prev = this.runs.get(e.runId) ?? this.blankRun(e, "running");
    const next: RunStream = { ...prev, updatedAt: prev.updatedAt + 1 };
    if (e.channel === "stderr") next.stderr = cap(next.stderr + e.textDelta);
    else next.stdout = cap(next.stdout + e.textDelta);
    if (e.provider) next.provider = e.provider;
    this.runs.set(e.runId, next);
  }

  private touchRun(e: StreamEvent, status: RunStream["status"]): void {
    if (!e.runId) return;
    const prev = this.runs.get(e.runId) ?? this.blankRun(e, status);
    this.runs.set(e.runId, { ...prev, status, updatedAt: prev.updatedAt + 1 });
  }

  private structural(e: StreamEvent): void {
    this.structuralRev++;
    this.recent = [...this.recent, e].slice(-RECENT_CAP);
  }
}

export const streamStore = new StreamStore();

/* ------------------------------------------------------------------- hooks */

export function useConnection(): StreamConnection {
  return useSyncExternalStore(streamStore.subscribe, streamStore.getConnection);
}

/** A counter that bumps on every structural event — add to a poll effect's deps
 *  to refetch snapshots event-driven instead of waiting for the next interval. */
export function useStructuralRevision(): number {
  return useSyncExternalStore(streamStore.subscribe, streamStore.getStructuralRev);
}

export function useRunStream(runId: string | null | undefined): RunStream | undefined {
  return useSyncExternalStore(streamStore.subscribe, () => streamStore.getRun(runId));
}

export function useRecentEvents(): StreamEvent[] {
  return useSyncExternalStore(streamStore.subscribe, streamStore.getRecent);
}

/* --------------------------------------------------------------- provider */

/** Owns the single SSE connection for the active workspace, with a polling
 *  fallback. Mount once near the app root. */
export function EventStreamProvider({
  workspacePath,
  children,
}: {
  workspacePath: string | null;
  children: ReactNode;
}) {
  useEffect(() => {
    streamStore.reset();
    if (!workspacePath) return;

    let stopped = false;
    let es: EventSource | null = null;
    let pollTimer: number | undefined;
    let opened = false;

    const startPolling = () => {
      streamStore.setConnection("polling");
      const tick = async () => {
        if (stopped) return;
        if (!document.hidden) {
          try {
            const res = await fetch(`/api/events?cursor=${streamStore.cursor}`);
            if (res.ok) {
              const j = await res.json();
              (j.events ?? []).forEach((raw: unknown) => {
                const ev = coerceStreamEvent(raw);
                if (ev) streamStore.apply(ev);
              });
            }
          } catch {
            /* keep retrying quietly */
          }
        }
        pollTimer = window.setTimeout(tick, POLL_MS);
      };
      void tick();
    };

    const startSSE = () => {
      if (typeof EventSource === "undefined") {
        startPolling();
        return;
      }
      try {
        es = new EventSource(`/api/events/stream?cursor=${streamStore.cursor}`);
      } catch {
        startPolling();
        return;
      }
      es.onopen = () => {
        opened = true;
        streamStore.setConnection("live");
      };
      es.onmessage = (m) => {
        try {
          const ev = coerceStreamEvent(JSON.parse(m.data));
          if (ev) streamStore.apply(ev);
        } catch {
          /* ignore malformed frame */
        }
      };
      es.onerror = () => {
        if (stopped) return;
        if (!opened) {
          // SSE never connected — fall back to polling for good.
          es?.close();
          es = null;
          startPolling();
        } else {
          // Transient drop; the browser auto-reconnects. Show degraded until onopen.
          streamStore.setConnection("polling");
        }
      };
    };

    startSSE();
    return () => {
      stopped = true;
      es?.close();
      if (pollTimer) window.clearTimeout(pollTimer);
    };
  }, [workspacePath]);

  return <>{children}</>;
}
