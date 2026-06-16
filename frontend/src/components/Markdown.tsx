import { Fragment, useState, type ReactNode } from "react";

/* Shared compact-markdown renderer. Agent replies (chat bubbles AND task step
   outputs) are markdown prose: headings, bullets, numbered lists, tables,
   **bold**, `code`, fenced code blocks, and AgentFlow directive blocks. This
   renders them readably instead of as a raw monospace dump, and replaces
   pipeline step ids with colored chips. One renderer, used on every surface. */

const COLLAPSE_CHARS = 700; // longer bodies start collapsed ("Show more")

/* --------------------------------------------------------- step color system
   One hue per pipeline role: Spec=sky · Implement=indigo · QA=teal ·
   Review=fuchsia · Fix=orange */

export const STEP_META: Record<string, { label: string; chip: string; dot: string }> = {
  codex_spec: {
    label: "Spec",
    chip: "border-sky-300 bg-sky-50 text-sky-700 dark:border-sky-800 dark:bg-sky-950/50 dark:text-sky-300",
    dot: "bg-sky-500",
  },
  claude_implement: {
    label: "Implement",
    chip: "border-indigo-300 bg-indigo-50 text-indigo-700 dark:border-indigo-800 dark:bg-indigo-950/50 dark:text-indigo-300",
    dot: "bg-indigo-500",
  },
  gemini_qa: {
    label: "QA",
    chip: "border-teal-300 bg-teal-50 text-teal-700 dark:border-teal-800 dark:bg-teal-950/50 dark:text-teal-300",
    dot: "bg-teal-500",
  },
  codex_review: {
    label: "Review",
    chip: "border-fuchsia-300 bg-fuchsia-50 text-fuchsia-700 dark:border-fuchsia-800 dark:bg-fuchsia-950/50 dark:text-fuchsia-300",
    dot: "bg-fuchsia-500",
  },
  claude_fix: {
    label: "Fix",
    chip: "border-orange-300 bg-orange-50 text-orange-700 dark:border-orange-800 dark:bg-orange-950/50 dark:text-orange-300",
    dot: "bg-orange-500",
  },
};

const STEP_ALIASES: Record<string, string> = {
  spec: "codex_spec",
  implement: "claude_implement",
  qa: "gemini_qa",
  review: "codex_review",
  fix: "claude_fix",
  "fix bugs": "claude_fix",
  "qa / test": "gemini_qa",
  "write spec": "codex_spec",
  "final review": "codex_review",
};

function stepMeta(raw: string) {
  const key = raw.trim().toLowerCase();
  return STEP_META[key] ?? STEP_META[STEP_ALIASES[key] ?? ""];
}

export function StepChip({ name }: { name: string }) {
  const meta = stepMeta(name);
  if (!meta) {
    return <span className="chip">{name}</span>;
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold ${meta.chip}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} aria-hidden="true" />
      {meta.label}
    </span>
  );
}

const STEP_TOKEN_RE = /(codex_spec|claude_implement|gemini_qa|codex_review|claude_fix)/g;

/** Replace step ids inside prose with colored chips. */
export function withStepChips(text: string): ReactNode[] {
  return text.split(STEP_TOKEN_RE).map((part, i) =>
    STEP_META[part] ? <StepChip key={i} name={part} /> : <Fragment key={i}>{part}</Fragment>,
  );
}

/* ------------------------------------------------- message rendering helpers */

type Segment = { kind: "text"; text: string } | { kind: "code"; lang: string; code: string };

function parseSegments(content: string): Segment[] {
  const segments: Segment[] = [];
  const re = /```([\w-]*)\s*\n([\s\S]*?)```/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(content)) !== null) {
    if (m.index > last) segments.push({ kind: "text", text: content.slice(last, m.index) });
    segments.push({ kind: "code", lang: m[1] ?? "", code: m[2] ?? "" });
    last = re.lastIndex;
  }
  if (last < content.length) segments.push({ kind: "text", text: content.slice(last) });
  return segments;
}

/** Minimal inline markdown: **bold** and `code`, plus colored step chips. */
function renderInline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{withStepChips(part.slice(2, -2))}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      const inner = part.slice(1, -1);
      const meta = stepMeta(inner);
      if (meta) return <StepChip key={i} name={inner} />;
      return (
        <code key={i} className="rounded bg-neutral-100 px-1 font-mono text-[10px] dark:bg-neutral-700/60">
          {inner}
        </code>
      );
    }
    return <Fragment key={i}>{withStepChips(part)}</Fragment>;
  });
}

function MdTable({ rows }: { rows: string[] }) {
  const parse = (r: string) =>
    r.replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
  const header = parse(rows[0]);
  const body = rows
    .slice(1)
    .filter((r) => !/^\|?[\s\-:|]+\|?$/.test(r))
    .map(parse);
  return (
    <div className="my-1.5 overflow-x-auto rounded-md border border-neutral-200 dark:border-neutral-700">
      <table className="w-full text-[11px]">
        <thead>
          <tr className="border-b border-neutral-200 bg-neutral-50 text-left dark:border-neutral-700 dark:bg-neutral-900/60">
            {header.map((h, i) => (
              <th key={i} className="px-2 py-1 font-semibold">
                {renderInline(h)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, i) => (
            <tr key={i} className="border-b border-neutral-100 last:border-0 dark:border-neutral-800">
              {row.map((cell, j) => (
                <td key={j} className="px-2 py-1 align-top">
                  {renderInline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TextBlock({ text }: { text: string }) {
  const lines = text.split("\n");
  const out: ReactNode[] = [];
  let i = 0;
  let key = 0;
  while (i < lines.length) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith("|") && trimmed.includes("|", 1)) {
      const tbl: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        tbl.push(lines[i].trim());
        i++;
      }
      out.push(<MdTable key={key++} rows={tbl} />);
      continue;
    }
    if (!trimmed) {
      out.push(<div key={key++} className="h-1.5" />);
    } else if (/^#{1,4}\s/.test(trimmed)) {
      out.push(
        <div key={key++} className="pt-1 text-xs font-semibold">
          {renderInline(trimmed.replace(/^#{1,4}\s/, ""))}
        </div>,
      );
    } else if (/^[-*]\s+/.test(trimmed)) {
      out.push(
        <div key={key++} className="flex gap-1.5 pl-1">
          <span className="text-accent-subtle">•</span>
          <span className="min-w-0 flex-1">{renderInline(trimmed.replace(/^[-*]\s+/, ""))}</span>
        </div>,
      );
    } else if (/^\d+\.\s+/.test(trimmed)) {
      const num = trimmed.match(/^(\d+)\./)![1];
      out.push(
        <div key={key++} className="flex gap-1.5 pl-1">
          <span className="font-semibold tabular-nums text-accent-subtle">{num}.</span>
          <span className="min-w-0 flex-1">{renderInline(trimmed.replace(/^\d+\.\s+/, ""))}</span>
        </div>,
      );
    } else {
      out.push(<div key={key++}>{renderInline(lines[i])}</div>);
    }
    i++;
  }
  return <div className="space-y-0.5">{out}</div>;
}

/* --------------------------------------------------------- directive cards */

const DIRECTIVE_STYLE: Record<string, { label: string; cls: string }> = {
  "agentflow-task": {
    label: "Created task",
    cls: "border-blue-200 bg-blue-50/70 text-blue-700 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300",
  },
  "agentflow-queue": {
    label: "Queued steps",
    cls: "border-violet-200 bg-violet-50/70 text-violet-700 dark:border-violet-900 dark:bg-violet-950/40 dark:text-violet-300",
  },
  "agentflow-done": {
    label: "Task complete",
    cls: "border-emerald-200 bg-emerald-50/70 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300",
  },
  "agentflow-needs-user": {
    label: "Needs your decision",
    cls: "border-amber-200 bg-amber-50/70 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300",
  },
  "agentflow-run": {
    label: "Ran command",
    cls: "border-neutral-300 bg-neutral-100 text-neutral-700 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300",
  },
};

/** AgentFlow directive blocks render as colored action cards instead of raw code. */
function DirectiveCard({ lang, code }: { lang: string; code: string }) {
  const style = DIRECTIVE_STYLE[lang] ?? DIRECTIVE_STYLE["agentflow-queue"];
  const fields: Record<string, string> = {};
  for (const line of code.split("\n")) {
    const idx = line.indexOf(":");
    if (idx > 0) fields[line.slice(0, idx).trim().toLowerCase()] = line.slice(idx + 1).trim();
  }
  const steps = (fields.steps ?? (fields.queue === "full" ? "codex_spec,claude_implement,gemini_qa,codex_review" : fields.queue) ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return (
    <div className={`my-1.5 rounded-md border px-2.5 py-1.5 ${style.cls}`}>
      <div className="text-[10px] font-semibold uppercase tracking-wide">{style.label}</div>
      {fields.title && <div className="mt-0.5 text-xs font-medium text-neutral-800 dark:text-neutral-100">{fields.title}</div>}
      {fields.command && (
        <div className="mt-0.5 font-mono text-[11px] text-neutral-800 dark:text-neutral-200">$ {fields.command}</div>
      )}
      {fields.reason && <div className="mt-0.5 text-xs text-neutral-700 dark:text-neutral-300">{fields.reason}</div>}
      {fields.goal && <div className="mt-0.5 text-[11px] text-neutral-600 dark:text-neutral-400">{fields.goal}</div>}
      {steps.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {steps.map((s) => (
            <StepChip key={s} name={s} />
          ))}
        </div>
      )}
    </div>
  );
}

/** A markdown body: directive cards + code blocks + prose, collapsible when long.
 *  `fade` lets a caller match the collapse gradient to its own background. */
export function Markdown({
  content,
  fade = "from-white to-transparent dark:from-neutral-800",
}: {
  content: string;
  fade?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const long = content.length > COLLAPSE_CHARS;
  const segments = parseSegments(content);
  return (
    <div>
      <div className={long && !expanded ? "relative max-h-40 overflow-hidden" : ""}>
        {segments.map((seg, i) =>
          seg.kind === "code" ? (
            seg.lang.startsWith("agentflow-") ? (
              <DirectiveCard key={i} lang={seg.lang} code={seg.code} />
            ) : (
              <pre key={i} className="mono-block my-1 max-h-48 whitespace-pre-wrap text-[10px]">
                {seg.code.trim()}
              </pre>
            )
          ) : (
            <TextBlock key={i} text={seg.text.trim()} />
          ),
        )}
        {long && !expanded && (
          <div className={`pointer-events-none absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t ${fade}`} />
        )}
      </div>
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
