import { Fragment, useEffect, useRef, useState } from "react";
import ArtifactChip from "../../components/ArtifactChip";
import LiveActivityFeed from "../../components/LiveActivityFeed";
import { Markdown } from "../../components/Markdown";
import RawDetail from "../../components/RawDetail";
import StatusBadge from "../../components/StatusBadge";
import { Disclosure } from "../../components/TaskViews";
import { Spinner } from "../../components/icons";
import { parsePrompt } from "../../lib/taskFormat";
import { useRunStream } from "../../stream";
import type { Exchange, StepState, TaskDetail } from "../../types";
import { SHORT_LABELS } from "./taskPageModel";

/* Per-step palette: a left accent spine + a faint header tint keep each step's
   identity without the old crude colored top border. */
const STEP_COLOR: Record<string, { dot: string; accent: string; tint: string }> = {
  codex_spec: {
    dot: "bg-sky-500",
    accent: "border-l-sky-400",
    tint: "bg-sky-50/50 dark:bg-sky-950/20",
  },
  claude_implement: {
    dot: "bg-indigo-500",
    accent: "border-l-indigo-400",
    tint: "bg-indigo-50/50 dark:bg-indigo-950/20",
  },
  gemini_qa: {
    dot: "bg-teal-500",
    accent: "border-l-teal-400",
    tint: "bg-teal-50/50 dark:bg-teal-950/20",
  },
  codex_review: {
    dot: "bg-fuchsia-500",
    accent: "border-l-fuchsia-400",
    tint: "bg-fuchsia-50/50 dark:bg-fuchsia-950/20",
  },
  claude_fix: {
    dot: "bg-orange-500",
    accent: "border-l-orange-400",
    tint: "bg-orange-50/50 dark:bg-orange-950/20",
  },
};

function LongText({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = text.length > 600;
  return (
    <div>
      <p
        className={`whitespace-pre-wrap break-words text-[11px] leading-relaxed text-neutral-600 dark:text-neutral-300 ${
          long && !expanded ? "max-h-20 overflow-hidden" : ""
        }`}
      >
        {text}
      </p>
      {long && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="focusable mt-1 cursor-pointer rounded text-[10px] font-medium text-blue-600 hover:underline dark:text-blue-400"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}

function fmtStamp(stamp: string): string {
  const t = stamp.split("-")[1] ?? "";
  return t.length === 6 ? `${t.slice(0, 2)}:${t.slice(2, 4)}:${t.slice(4, 6)}` : stamp;
}

export default function StepChat({
  detail,
  step,
  exchanges,
  onRun,
  onOpenFile,
}: {
  detail: TaskDetail;
  step: string;
  exchanges: Exchange[];
  onRun: () => void;
  onOpenFile: (name: string) => void;
}) {
  const preview = detail.stepPreviews[step];
  const state: StepState = detail.task.steps[step] ?? { status: "idle" };
  const liveRun = detail.runs.find((run) => run.step === step && run.status === "running");
  // Active text comes from the shared event store only — never the polled
  // run-snapshot's stdout (revamp Workstream 1 data rule).
  const stream = useRunStream(liveRun?.id);
  const liveText = (stream?.stdout ?? "") + (stream?.stderr ?? "");
  const involved = state.status !== "idle" || exchanges.length > 0;
  const color = STEP_COLOR[step];
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [exchanges.length, liveText]);

  return (
    <div
      className={`card overflow-hidden border-l-2 ${color.accent} transition-opacity ${involved ? "" : "opacity-60"}`}
      id={`step-${step}`}
    >
      <div
        className={`flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-neutral-200/70 px-3 py-2 dark:border-neutral-800 ${color.tint}`}
      >
        <span className={`h-2 w-2 shrink-0 rounded-full ${color.dot}`} aria-hidden="true" />
        <span className="shrink-0 text-xs font-semibold">{SHORT_LABELS[step]}</span>
        <span className="min-w-0 truncate font-mono text-[10px] text-neutral-400">
          {preview?.provider}
        </span>
        {state.status !== "idle" && <StatusBadge state={state.status} />}
        <button
          className="btn-secondary btn-xs ml-auto"
          onClick={onRun}
          disabled={state.status === "running"}
        >
          {state.status === "running" ? "Running…" : "Run"}
        </button>
      </div>

      {((state.artifactsWritten?.length ?? 0) > 0 || (state.codeChanged?.length ?? 0) > 0) && (
        <div className="flex flex-wrap items-center gap-1 border-b border-neutral-100 px-3 py-1.5 dark:border-neutral-800/60">
          {(state.artifactsWritten ?? []).map((artifact) => (
            <ArtifactChip key={artifact} name={artifact} onOpen={onOpenFile} />
          ))}
          {(state.codeChanged?.length ?? 0) > 0 && (
            <span
              className="rounded border border-violet-300 bg-violet-50 px-1.5 py-0.5 font-mono text-[10px] text-violet-700 dark:border-violet-800 dark:bg-violet-950/40 dark:text-violet-300"
              title={state.codeChanged?.join("\n")}
            >
              code: {state.codeChanged?.length}
            </span>
          )}
        </div>
      )}

      <div ref={scrollRef} className="max-h-96 min-h-24 flex-1 space-y-2 overflow-y-auto p-3">
        {exchanges.length === 0 && !liveRun ? (
          <p className="text-[11px] text-neutral-400">
            {involved ? "Queued - nothing sent yet." : "Not used in this task."}
          </p>
        ) : (
          exchanges.map((exchange, idx) => {
            const brief = parsePrompt(exchange.prompt).brief || exchange.prompt;
            const isLive = idx === exchanges.length - 1 && !!liveRun && !exchange.output.trim();
            const hasOutput = exchange.output.trim().length > 0;

            // A finished exchange with no output (e.g. a cancelled run) collapses to
            // one muted line instead of a "No output." bubble — still inspectable.
            if (!isLive && !hasOutput) {
              return (
                <Disclosure
                  key={exchange.stamp}
                  label={`${preview?.provider ?? "agent"} · no reply · ${fmtStamp(exchange.stamp)}`}
                  className="pl-1 opacity-80"
                >
                  {exchange.prompt && (
                    <RawDetail text={exchange.prompt} label="prompt" kind="prompt" pageSize={50} />
                  )}
                </Disclosure>
              );
            }

            return (
              <Fragment key={exchange.stamp}>
                {/* The brief (the prompt/context sent to the agent) is collapsed by
                    default — the agent's reply is the focus; expand to inspect it. */}
                <Disclosure label={`brief · ${fmtStamp(exchange.stamp)}`}>
                  <div className="rounded-lg border border-blue-200/70 bg-blue-50/40 px-3 py-2 dark:border-blue-900/60 dark:bg-blue-950/20">
                    <LongText text={brief} />
                  </div>
                </Disclosure>
                {!isLive && (
                  <div className="rounded-xl border border-neutral-200 bg-white px-3 py-2 dark:border-neutral-700/80 dark:bg-neutral-900">
                    <div className="mb-1 flex items-center gap-1.5 text-[10px] font-medium text-neutral-400">
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${color.dot}`}
                        aria-hidden="true"
                      />
                      <span className="font-mono">{preview?.provider}</span>
                      <span>reply</span>
                    </div>
                    <Markdown
                      content={exchange.output}
                      fade="from-white to-transparent dark:from-neutral-900"
                      onOpenFile={onOpenFile}
                    />
                  </div>
                )}
                {!isLive && (
                  <Disclosure label="Raw prompt / output" className="pl-1">
                    <div className="space-y-1.5">
                      {exchange.prompt && (
                        <RawDetail
                          text={exchange.prompt}
                          label="prompt"
                          kind="prompt"
                          pageSize={50}
                        />
                      )}
                      {exchange.output && (
                        <RawDetail
                          text={exchange.output}
                          label="output"
                          kind="stdout"
                          pageSize={50}
                        />
                      )}
                    </div>
                  </Disclosure>
                )}
              </Fragment>
            );
          })
        )}
        {liveRun && (
          <div className="flex justify-start">
            <div className="w-full max-w-[94%] rounded-xl rounded-bl-sm border border-blue-200 bg-white px-3 py-2 dark:border-blue-900 dark:bg-neutral-900">
              <div className="mb-1 flex items-center gap-1.5 text-[10px] font-medium text-blue-500">
                <Spinner className="h-3 w-3" />
                <span className="font-mono">{liveRun.provider}</span>
                <span>working…</span>
              </div>
              {/* The agent's actual activity — narration, commands, results —
                  parsed from the live stream, not a raw log tail. */}
              <LiveActivityFeed
                provider={liveRun.provider}
                stdout={stream?.stdout ?? ""}
                stderr={stream?.stderr ?? ""}
                active
                className="border-0 bg-transparent px-0 py-0 dark:bg-transparent"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
