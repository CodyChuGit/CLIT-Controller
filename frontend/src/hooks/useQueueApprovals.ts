import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import { useStructuralRevision } from "../stream";
import type { Approval, QueueState } from "../types";

/* Shared queue + pending-approvals data layer (I/O rebuild — removes TasksPage's
   page-local polling of event-covered state). Polls every 3s and refetches on a
   structural stream event. `setQueue` is exposed for the optimistic updates the
   queue actions (approve/retry/skip/reroute/remove) apply. */
export function useQueueApprovals() {
  const [queue, setQueue] = useState<QueueState | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const streamRev = useStructuralRevision();

  const reload = useCallback(async () => {
    try {
      const [q, appr] = await Promise.all([
        api.queue(),
        api.approvals(true).catch(() => ({ approvals: [] as Approval[] })),
      ]);
      setQueue(q);
      setApprovals(appr.approvals);
    } catch {
      /* no workspace or backend away */
    }
  }, []);

  useEffect(() => {
    void reload();
    const id = window.setInterval(reload, 3000);
    return () => window.clearInterval(id);
  }, [reload, streamRev]);

  return { queue, setQueue, approvals, reload };
}
