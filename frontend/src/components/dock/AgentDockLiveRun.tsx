import { LiveRunActivity } from "../LiveActivityFeed";

/** Live output for one run, read from the shared event store only — never from
 *  polled log snapshots (revamp Workstream 1 data rule). Rendered as a
 *  followable activity feed (narration / tool calls / results), not raw log. */
export default function AgentDockLiveRun({
  runId,
  provider,
  className,
}: {
  runId: string | null | undefined;
  provider?: string | null;
  className?: string;
}) {
  return <LiveRunActivity runId={runId} provider={provider} className={className} />;
}
