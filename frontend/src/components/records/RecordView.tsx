import type { PresentationRecord } from "../../lib/presentation";
import RawDetail from "../RawDetail";

/* Presentation-record components (I/O rebuild). Each renders one semantic record
   kind; RecordView selects by `record.kind` — never by sniffing text. Shared by
   every surface so commands/failures/summaries look and behave consistently. */

const STATUS_STYLE: Record<string, string> = {
  running: "text-blue-600 dark:text-blue-400",
  succeeded: "text-emerald-600 dark:text-emerald-400",
  failed: "text-rose-600 dark:text-rose-400",
  cancelled: "text-amber-600 dark:text-amber-400",
  error: "text-rose-600 dark:text-rose-400",
};

export function CommandRecord({
  command,
  output,
  status,
  exitCode,
  durationMs,
}: Extract<PresentationRecord, { kind: "command" }>) {
  return (
    <div className="rounded-md border border-neutral-200 bg-white px-2.5 py-1.5 dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex items-center gap-2 text-[11px]">
        {command && (
          <code className="min-w-0 flex-1 truncate font-mono text-neutral-700 dark:text-neutral-300">
            $ {command}
          </code>
        )}
        {status && <span className={`font-medium ${STATUS_STYLE[status] ?? ""}`}>{status}</span>}
        {exitCode != null && <span className="tabular-nums text-neutral-400">exit {exitCode}</span>}
        {durationMs != null && (
          <span className="tabular-nums text-neutral-400">{(durationMs / 1000).toFixed(1)}s</span>
        )}
      </div>
      {output && <RawDetail text={output} kind="stdout" pageSize={50} className="mt-1" />}
    </div>
  );
}

export function FailureRecord({
  title,
  summary,
}: Extract<PresentationRecord, { kind: "failure" }>) {
  return (
    <div
      role="alert"
      className="rounded-md border border-l-2 border-rose-200 border-l-rose-500 bg-rose-50/70 px-2.5 py-1.5 dark:border-rose-900 dark:bg-rose-950/40"
    >
      <div className="text-[11px] font-semibold text-rose-700 dark:text-rose-300">{title}</div>
      {summary && (
        <div className="mt-0.5 text-[11px] text-neutral-700 dark:text-neutral-300">{summary}</div>
      )}
    </div>
  );
}

export function SummaryRecord({ summaryKind }: Extract<PresentationRecord, { kind: "summary" }>) {
  return (
    <div className="rounded-md border border-emerald-200 bg-emerald-50/60 px-2.5 py-1.5 text-[11px] text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300">
      <span className="font-semibold uppercase tracking-wide">
        {summaryKind.replace(/_/g, " ")}
      </span>{" "}
      ready
    </div>
  );
}

/** Select the component for a record by its deterministic kind. Returns null for
    record kinds rendered elsewhere (narrative → conversation Message; approval →
    the shared ApprovalCard; cancellation → inline activity). */
export default function RecordView({ record }: { record: PresentationRecord }) {
  switch (record.kind) {
    case "command":
      return <CommandRecord {...record} />;
    case "failure":
      return <FailureRecord {...record} />;
    case "summary":
      return <SummaryRecord {...record} />;
    default:
      return null;
  }
}
