import { Fragment, useEffect, useRef, useState } from "react";
import ArtifactChip from "../../components/ArtifactChip";
import { Markdown } from "../../components/Markdown";
import RawDetail from "../../components/RawDetail";
import SmoothStreamingText from "../../components/SmoothStreamingText";
import StatusBadge from "../../components/StatusBadge";
import { Disclosure } from "../../components/TaskViews";
import { Spinner } from "../../components/icons";
import { parsePrompt } from "../../lib/taskFormat";
import { useRunStream } from "../../stream";
import type { Exchange, StepState, TaskDetail } from "../../types";
import { SHORT_LABELS } from "./taskPageModel";

const STEP_COLOR: Record<string, { dot: string; border: string }> = {
  codex_spec: { dot: "bg-sky-500", border: "border-t-sky-400" },
  claude_implement: { dot: "bg-indigo-500", border: "border-t-indigo-400" },
  gemini_qa: { dot: "bg-teal-500", border: "border-t-teal-400" },
  codex_review: { dot: "bg-fuchsia-500", border: "border-t-fuchsia-400" },
  claude_fix: { dot: "bg-orange-500", border: "border-t-orange-400" },
};

function LongText({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = text.length > 600;
  return (
    <div>
      <pre
        className={`whitespace-pre-wrap break-words font-mono text-[10px] leading-relaxed text-neutral-700 dark:text-neutral-300 ${
          long && !expanded ? "max-h-28 overflow-hidden" : ""
        }`}
      >
        {text}
      </pre>
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
  const stream = useRunStream(liveRun?.id);
  const liveText = stream?.stdout || liveRun?.stdout || "";
  const involved = state.status !== "idle" || exchanges.length > 0;
  const color = STEP_COLOR[step];
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [exchanges.length, liveText]);

  return (
    <div
      className={`card border-t-2 ${color.border} ${involved ? "" : "opacity-50"}`}
      id={`step-${step}`}
    >
      <div className="flex items-center gap-2 border-b border-neutral-100 px-3 py-2 dark:border-neutral-800/60">
        <span className={`h-2 w-2 rounded-full ${color.dot}`} aria-hidden="true" />
        <span className="text-xs font-semibold">{SHORT_LABELS[step]}</span>
        <span className="font-mono text-[10px] text-neutral-400">{preview?.provider}</span>
        {state.status !== "idle" && <StatusBadge state={state.status} />}
        <span className="flex-1" />
        <button
          className="btn-secondary btn-xs"
          onClick={onRun}
          disabled={state.status === "running"}
        >
          {state.status === "running" ? "Running..." : "Run"}
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
            return (
              <Fragment key={exchange.stamp}>
                <div className="flex justify-end">
                  <div className="max-w-[94%] rounded-lg rounded-br-sm border border-blue-200 bg-blue-50/60 px-2.5 py-1.5 dark:border-blue-900 dark:bg-blue-950/30">
                    <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-blue-600/80 dark:text-blue-300/80">
                      task brief - {fmtStamp(exchange.stamp)}
                    </div>
                    <LongText text={brief} />
                  </div>
                </div>
                {!isLive && (
                  <div className="flex justify-start">
                    <div className="max-w-[94%] rounded-lg rounded-bl-sm border border-neutral-200 bg-white px-2.5 py-1.5 dark:border-neutral-700 dark:bg-neutral-900">
                      <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-neutral-400">
                        {preview?.provider} - reply
                      </div>
                      {exchange.output.trim() ? (
                        <Markdown
                          content={exchange.output}
                          fade="from-white to-transparent dark:from-neutral-900"
                        />
                      ) : (
                        <p className="text-[11px] italic text-neutral-400">No output.</p>
                      )}
                    </div>
                  </div>
                )}
                {!isLive && (exchange.prompt || exchange.output) && (
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
            <div className="max-w-[94%] rounded-lg rounded-bl-sm border border-blue-200 bg-white px-2.5 py-1.5 dark:border-blue-900 dark:bg-neutral-900">
              <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-blue-500">
                <Spinner className="h-3 w-3" /> {liveRun.provider} - working...
              </div>
              {liveText && (
                <pre className="max-h-28 overflow-hidden whitespace-pre-wrap break-words font-mono text-[10px] leading-relaxed text-neutral-500">
                  <SmoothStreamingText text={liveText} active mode="mono" maxChars={1200} />
                </pre>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
