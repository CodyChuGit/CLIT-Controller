import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Card } from "./ui";
import type { ContextReport } from "../types";

function formatNumber(value: number) {
  return Number.isFinite(value) ? value.toLocaleString() : "0";
}

function formatScore(value: number) {
  return Number.isFinite(value) ? value.toFixed(2) : "0.00";
}

function formatPct(value: number) {
  return Number.isFinite(value) ? `${value.toFixed(1)}%` : "0.0%";
}

function FieldPill({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded bg-neutral-100 px-1.5 py-0.5 text-[11px] text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400">
      {label}
      <strong className="font-mono font-semibold text-neutral-700 dark:text-neutral-200">
        {value}
      </strong>
    </span>
  );
}

function ResultList({ report }: { report: ContextReport }) {
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <section>
        <h3 className="section-title mb-1.5">Selected files</h3>
        {report.selectedFiles.length === 0 ? (
          <p className="text-xs text-neutral-400">No files selected.</p>
        ) : (
          <ul className="divide-y divide-neutral-100 dark:divide-neutral-800">
            {report.selectedFiles.map((file) => (
              <li key={file.path} className="py-2 first:pt-0 last:pb-0">
                <div className="flex items-start gap-2">
                  <span
                    className="min-w-0 flex-1 truncate font-mono text-xs font-medium text-neutral-800 dark:text-neutral-200"
                    title={file.path}
                  >
                    {file.path}
                  </span>
                  <span className="shrink-0 font-mono text-[11px] text-neutral-400">
                    {formatScore(file.score)}
                  </span>
                </div>
                <p className="mt-0.5 text-[11px] text-neutral-500">
                  {file.reasons.length > 0 ? file.reasons.join(", ") : "No reasons provided."}
                </p>
                {file.excerpt && (
                  <pre className="mt-1 max-h-16 overflow-hidden whitespace-pre-wrap break-words rounded bg-neutral-50 p-1.5 font-mono text-[10px] leading-relaxed text-neutral-500 dark:bg-neutral-950 dark:text-neutral-400">
                    {file.excerpt}
                    {file.excerptTruncated ? "\n..." : ""}
                  </pre>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="section-title mb-1.5">Rejected candidates</h3>
        {report.rejectedCandidates.length === 0 ? (
          <p className="text-xs text-neutral-400">No rejected candidates.</p>
        ) : (
          <ul className="divide-y divide-neutral-100 dark:divide-neutral-800">
            {report.rejectedCandidates.map((candidate) => (
              <li key={candidate.path} className="py-2 first:pt-0 last:pb-0">
                <div className="flex items-start gap-2">
                  <span
                    className="min-w-0 flex-1 truncate font-mono text-xs font-medium text-neutral-800 dark:text-neutral-200"
                    title={candidate.path}
                  >
                    {candidate.path}
                  </span>
                  <span className="shrink-0 font-mono text-[11px] text-neutral-400">
                    {formatScore(candidate.score)}
                  </span>
                </div>
                <p className="mt-0.5 text-[11px] text-neutral-500">{candidate.reason}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

export default function ContextIntelligencePanel() {
  const [task, setTask] = useState("");
  const [report, setReport] = useState<ContextReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const preview = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = task.trim();
    if (!trimmed) {
      setError("Enter a task to preview context.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setReport(await api.contextPreview(trimmed));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="Context Intelligence" pad>
      <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => void preview(e)}>
        <input
          className="input"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="Task to preview context for"
        />
        <button className="btn-primary shrink-0" disabled={loading || !task.trim()}>
          {loading ? "Previewing..." : "Preview context"}
        </button>
      </form>

      {error && (
        <p className="mt-2 rounded-md border border-rose-200 bg-rose-50 px-2 py-1.5 text-xs text-rose-700 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-300">
          {error}
        </p>
      )}

      {report && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="chip" title="Report id">
              {report.id}
            </span>
            <span className="text-[11px] text-neutral-400">{report.kind}</span>
            <span className="text-[11px] text-neutral-400">{report.policyLevel}</span>
            <span className="text-[11px] text-neutral-400">{report.createdAt}</span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="section-title mr-1">Tokens</span>
            <FieldPill label="before" value={formatNumber(report.tokenUsage.tokensBefore)} />
            <FieldPill label="after" value={formatNumber(report.tokenUsage.tokensAfter)} />
            <FieldPill label="saved" value={formatPct(report.tokenUsage.savingsPct)} />
          </div>

          <ResultList report={report} />

          <section>
            <h3 className="section-title mb-1.5">Session digest</h3>
            <p className="max-h-16 overflow-hidden whitespace-pre-wrap text-xs leading-relaxed text-neutral-600 dark:text-neutral-300">
              {report.digest.text || "No digest text."}
            </p>
          </section>

          <details className="rounded-md border border-neutral-200 bg-neutral-50/70 dark:border-neutral-800 dark:bg-neutral-950/50">
            <summary className="focusable cursor-pointer px-2 py-1.5 text-xs font-medium text-neutral-500">
              Prompt preview
            </summary>
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words border-t border-neutral-200 p-2 font-mono text-[10px] leading-relaxed text-neutral-600 dark:border-neutral-800 dark:text-neutral-300">
              {report.promptPreview || "No prompt preview."}
            </pre>
          </details>
        </div>
      )}
    </Card>
  );
}
