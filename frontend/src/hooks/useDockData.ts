import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api";
import { useStructuralRevision } from "../stream";
import type { Approval, ChatState, QueueState, RunInfo } from "../types";

/* The Agent Dock's data layer (see components/dock/AgentDock) — the components compose
   rendering rather than owning fetching/polling (I/O rebuild — dock
   decomposition). Owns chat/queue/logs/approvals loading, the visibility-aware
   poll timer (paused when hidden / collapsed-light), workspace reset, and the
   event-driven refetch. Returns derived `busy` and a `reload`. */
export function useDockData(workspacePath: string | null, open: boolean) {
  const hasWorkspace = Boolean(workspacePath);
  const [data, setData] = useState<ChatState | null>(null);
  const [queue, setQueue] = useState<QueueState | null>(null);
  const [running, setRunning] = useState<RunInfo[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const wsRef = useRef(workspacePath);
  const streamRev = useStructuralRevision();

  // Each workspace has its own chat — drop everything from the previous one.
  useEffect(() => {
    wsRef.current = workspacePath;
    setData(null);
    setQueue(null);
    setRunning([]);
    setApprovals([]);
  }, [workspacePath]);

  const reload = useCallback(async () => {
    const ws = workspacePath;
    if (!ws) return;
    try {
      // Collapsed, the dock only renders unread/activity dots from chat state —
      // skip the queue/logs/approvals payloads (logs can carry KBs of run tails).
      if (!open) {
        const chat = await api.chat();
        if (wsRef.current !== ws) return;
        setData(chat);
        return;
      }
      const [chat, q, logs, appr] = await Promise.all([
        api.chat(),
        api.queue(),
        api.logs(),
        api.approvals(true).catch(() => ({ approvals: [] as Approval[] })),
      ]);
      if (wsRef.current !== ws) return; // ignore stale responses
      setData(chat);
      setQueue(q);
      setRunning(logs.running);
      setApprovals(appr.approvals);
    } catch {
      /* backend banner covers outages */
    }
  }, [workspacePath, open]);

  const busy =
    data?.pending != null ||
    Object.values(data?.channelPending ?? {}).some((p) => p != null) ||
    (queue?.items ?? []).some((i) => i.status === "running") ||
    running.length > 0;

  // Poll while collapsed too (slowly); pause while the tab is hidden and refetch
  // once on return rather than polling a background tab forever.
  useEffect(() => {
    if (!hasWorkspace) return;
    const ms = !open ? 10000 : busy ? 2000 : 6000;
    let id: number | undefined;
    const start = () => {
      if (id === undefined) id = window.setInterval(reload, ms);
    };
    const stop = () => {
      if (id !== undefined) {
        window.clearInterval(id);
        id = undefined;
      }
    };
    const onVisibility = () => {
      if (document.hidden) stop();
      else {
        void reload();
        start();
      }
    };
    void reload();
    if (!document.hidden) start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
    // streamRev intentionally excluded — its own effect below drives event refetch
    // without tearing down the poll timer on every event.
  }, [open, hasWorkspace, reload, busy]);

  // Refetch immediately on a structural stream event, without disturbing the timer.
  useEffect(() => {
    if (!hasWorkspace || streamRev === 0) return;
    void reload();
  }, [streamRev, hasWorkspace, reload]);

  return { data, queue, running, approvals, busy, reload, setQueue };
}
