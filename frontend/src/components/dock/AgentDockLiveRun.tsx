import { LiveOutput } from "../TaskViews";
import { stripResultSentinel } from "../../lib/narrative";
import { useRunStream } from "../../stream";

/** Live output for one run, read from the shared event store ONLY — never from
 *  polled log snapshots or cached chat tails (revamp Workstream 1 data rule).
 *  streamStore already owns SSE + the /api/events polling fallback, dedupe, and
 *  cursor resume; this component is pure presentation on top of it. */
export default function AgentDockLiveRun({ runId }: { runId: string | null | undefined }) {
  const stream = useRunStream(runId);
  const text = stripResultSentinel(stream?.stdout ?? "");
  if (!text) return null;
  return <LiveOutput text={text} active={stream?.status === "running"} />;
}
