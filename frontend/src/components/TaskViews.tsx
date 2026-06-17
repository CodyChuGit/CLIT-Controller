import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight, Spinner, Terminal } from "./icons";
import SmoothStreamingText from "./SmoothStreamingText";
import StatusBadge from "./StatusBadge";
import type { Approval, RunInfo } from "../types";
import {
  describeCommand,
  formatDuration,
  shortPath,
  summarizeOutput,
  type BudgetSummary,
  type OutputSummary,
} from "../lib/taskFormat";

/* Purpose-built views for the Tasks tab. Each renders a compact, scannable
   summary by default and keeps the raw text behind a disclosure so nothing is
   lost for debugging. Styling reuses the shared design tokens. */

/** A small "View raw" disclosure row. Collapsed by default. */
export function Disclosure({
  label,
  children,
  className = "",
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className={className}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="focusable inline-flex cursor-pointer items-center gap-1 rounded text-[10px] font-medium text-neutral-400 transition-colors hover:text-blue-600 dark:hover:text-blue-400"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {label}
      </button>
      {open && <div className="mt-1">{children}</div>}
    </div>
  );
}

const HEALTH_DOT: Record<string, string> = {
  green: "bg-emerald-500",
  yellow: "bg-amber-500",
  red: "bg-rose-500",
};

/** Compact, collapsible budget/context summary. Repeated identical contexts
 *  collapse to one row with a "repeated N times" note. */
export function ContextSummary({ budget, repeated }: { budget: BudgetSummary; repeated: number }) {
  return (
    <div className="rounded-md border border-neutral-200 bg-neutral-50/70 px-2.5 py-1.5 dark:border-neutral-800 dark:bg-neutral-900/40">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px] text-neutral-500">
        <span className="font-semibold uppercase tracking-wide text-neutral-400">Context</span>
        {budget.mode && (
          <span className="font-medium text-neutral-600 dark:text-neutral-300">{budget.mode}</span>
        )}
        {budget.providers.map((p) => (
          <span key={p.name} className="inline-flex items-center gap-1">
            <span
              className={`h-1.5 w-1.5 rounded-full ${HEALTH_DOT[p.health] ?? "bg-neutral-400"}`}
              aria-hidden="true"
            />
            {p.name}
          </span>
        ))}
        {repeated > 1 && <span className="text-neutral-400">· repeated {repeated}×</span>}
      </div>
      <Disclosure label="View raw" className="mt-1">
        <pre className="mono-block max-h-48 whitespace-pre-wrap break-words text-[10px]">
          {budget.raw}
        </pre>
      </Disclosure>
    </div>
  );
}

/** Pills highlighting the meaningful bits of a log: errors, warnings, changed
 *  files, test tallies. */
function OutputHighlights({ summary }: { summary: OutputSummary }) {
  return (
    <div className="flex flex-wrap items-center gap-1">
      {summary.tests && (
        <span className="rounded border border-blue-200 bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-700 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300">
          {summary.tests}
        </span>
      )}
      {summary.errors.length > 0 && (
        <span className="rounded border border-rose-200 bg-rose-50 px-1.5 py-0.5 text-[10px] font-medium text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">
          {summary.errors.length} error{summary.errors.length > 1 ? "s" : ""}
        </span>
      )}
      {summary.warnings.length > 0 && (
        <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300">
          {summary.warnings.length} warning{summary.warnings.length > 1 ? "s" : ""}
        </span>
      )}
      {summary.changedFiles.map((f) => (
        <span
          key={f}
          className="rounded border border-violet-200 bg-violet-50 px-1.5 py-0.5 font-mono text-[10px] text-violet-700 dark:border-violet-900 dark:bg-violet-950/40 dark:text-violet-300"
          title={f}
        >
          {f.split("/").pop()}
        </span>
      ))}
    </div>
  );
}

/** Mono content that starts clamped and expands in place — keeps long logs and
 *  agent replies skimmable without hiding the actual text behind a guessed
 *  one-line summary. */
function ClampedLog({ text, long }: { text: string; long: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <pre
        className={`whitespace-pre-wrap break-words font-mono text-[10px] leading-relaxed text-neutral-700 dark:text-neutral-300 ${
          long && !open ? "max-h-28 overflow-hidden" : ""
        }`}
      >
        {text}
      </pre>
      {long && (
        <button
          onClick={() => setOpen((v) => !v)}
          className="focusable mt-1 cursor-pointer rounded text-[10px] font-medium text-blue-600 hover:underline dark:text-blue-400"
        >
          {open ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

/** Log/reply output: highlight pills (errors, warnings, changed files, test
 *  tallies) over the real content, clamped and expandable. Raw text is always
 *  shown — never replaced by a guessed summary line. */
export function OutputView({ text }: { text: string }) {
  const summary = summarizeOutput(text);

  if (summary.empty) {
    return <p className="text-[11px] italic text-neutral-400">No output.</p>;
  }

  const hasHighlights =
    summary.tests != null ||
    summary.errors.length > 0 ||
    summary.warnings.length > 0 ||
    summary.changedFiles.length > 0;

  return (
    <div className="space-y-1.5">
      {hasHighlights && <OutputHighlights summary={summary} />}
      <ClampedLog text={summary.raw} long={summary.long} />
    </div>
  );
}

/** Live, auto-tailing output for an in-flight run — visible progress while a
 *  command/step is still moving (not a final-only snapshot). Tails the last
 *  ~2KB and pins the scroll to the bottom as new chunks arrive. */
export function LiveOutput({
  text,
  active = true,
  className = "",
}: {
  text: string;
  /** Animate while the run is live; finished output reveals instantly. */
  active?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLPreElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight; // auto-tail as new chunks arrive
  }, [text]);
  if (!text) return null;
  return (
    <pre
      ref={ref}
      className={`max-h-32 overflow-auto whitespace-pre-wrap break-words rounded border border-blue-200 bg-blue-50/50 p-1.5 font-mono text-[10px] leading-relaxed text-neutral-600 dark:border-blue-900 dark:bg-blue-950/30 dark:text-neutral-300 ${className}`}
    >
      <SmoothStreamingText text={text} active={active} mode="mono" maxChars={2000} />
    </pre>
  );
}

const APPROVAL_KIND_LABEL: Record<string, string> = {
  command: "command",
  install: "install",
  git_remote: "git",
  deploy: "deploy",
};

/** A pending approval hold rendered as a compact, actionable card: what the
 *  controller wants to run, why it needs sign-off, and Approve/Reject. The
 *  backend stays authoritative — these buttons hit the approval endpoints. */
export function ApprovalCard({
  approval,
  onApprove,
  onReject,
  busy = false,
}: {
  approval: Approval;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  busy?: boolean;
}) {
  const pending = approval.status === "pending";
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50/70 p-2.5 dark:border-amber-800 dark:bg-amber-950/30">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded border border-amber-300 bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:border-amber-800 dark:bg-amber-900/50 dark:text-amber-300">
          approval · {APPROVAL_KIND_LABEL[approval.kind] ?? approval.kind}
        </span>
        {approval.provider && <span className="chip">{approval.provider}</span>}
        <span className="flex-1" />
        {!pending && <StatusBadge state={approval.status} />}
      </div>
      <div className="mt-1.5 flex items-center gap-1.5 overflow-x-auto rounded bg-neutral-50 px-2 py-1 dark:bg-neutral-950">
        <span className="text-neutral-400">$</span>
        <code className="whitespace-pre font-mono text-[10px] text-neutral-700 dark:text-neutral-300">
          {approval.action}
        </code>
      </div>
      {approval.reason && (
        <p className="mt-1 text-[11px] leading-snug text-neutral-600 dark:text-neutral-400">
          {approval.reason}
        </p>
      )}
      {pending && (
        <div className="mt-2 flex items-center gap-1.5">
          <button
            className="btn-primary btn-xs"
            onClick={() => onApprove(approval.id)}
            disabled={busy}
          >
            Approve
          </button>
          <button
            className="btn-danger btn-xs"
            onClick={() => onReject(approval.id)}
            disabled={busy}
          >
            Reject
          </button>
        </div>
      )}
    </div>
  );
}

const CARD_STATUS: Record<string, { ring: string }> = {
  running: { ring: "border-l-blue-500" },
  succeeded: { ring: "border-l-emerald-500" },
  completed: { ring: "border-l-emerald-500" },
  ok: { ring: "border-l-emerald-500" },
  failed: { ring: "border-l-rose-500" },
  error: { ring: "border-l-rose-500" },
};

/** A single command rendered as a styled card: inferred title, the exact
 *  command, working dir, status, exit code, duration, and a summarized result
 *  with raw output behind a disclosure. */
export function CommandCard({ run }: { run: RunInfo }) {
  const title = describeCommand(run.commandPreview);
  const duration = formatDuration(run.durationMs);
  const cwd = shortPath(run.cwd);
  const merged = [run.stdout, run.stderr].filter(Boolean).join("\n");
  const accent = CARD_STATUS[run.status]?.ring ?? "border-l-neutral-300 dark:border-l-neutral-700";

  return (
    <div className={`card border-l-2 ${accent} p-2.5`}>
      <div className="flex flex-wrap items-center gap-2">
        <Terminal className="h-3.5 w-3.5 shrink-0 text-neutral-400" />
        <span className="text-xs font-semibold text-neutral-800 dark:text-neutral-200">
          {title}
        </span>
        {run.status === "running" ? (
          <Spinner className="h-3 w-3 text-blue-500" />
        ) : (
          <StatusBadge state={run.status} />
        )}
        <span className="flex-1" />
        {run.exitCode != null && (
          <span className="font-mono text-[10px] text-neutral-400">exit {run.exitCode}</span>
        )}
        {duration && <span className="font-mono text-[10px] text-neutral-400">{duration}</span>}
      </div>

      <div className="mt-1.5 flex items-center gap-1.5 overflow-x-auto rounded bg-neutral-50 px-2 py-1 dark:bg-neutral-950">
        <span className="text-neutral-400">$</span>
        <code className="whitespace-pre font-mono text-[10px] text-neutral-700 dark:text-neutral-300">
          {run.commandPreview}
        </code>
      </div>

      {cwd && (
        <p className="mt-1 font-mono text-[10px] text-neutral-400" title={run.cwd}>
          in {cwd}
        </p>
      )}

      {merged && (
        <div className="mt-1.5">
          <OutputView text={merged} />
        </div>
      )}
    </div>
  );
}
