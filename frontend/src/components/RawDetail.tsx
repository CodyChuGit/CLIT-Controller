import { useEffect, useMemo, useState } from "react";
import { stripAnsi } from "../lib/ansi";
import { ChevronLeft, ChevronRight } from "./icons";

// Kinds that are raw CLI streams and should have ANSI escapes normalized away for
// readable prose display (Pillar 3). Terminal panes use xterm and keep their ANSI.
const ANSI_KINDS: ReadonlySet<string> = new Set(["stdout", "stderr", "log"]);

/* Shared paginated, read-only viewer for machine-readable detail — raw prompts,
   stdout, stderr, logs, structured events, JSON, directives, and long diffs.
   Used by both the controller dock expanders and the Tasks page panels so raw
   data is always inspectable without a giant scrollback as the default. The
   backend has already redacted this text; this component never edits it. See
   docs/task-controller-io-surface.md §Raw Detail Pagination. */

export type RawKind =
  | "text"
  | "prompt"
  | "stdout"
  | "stderr"
  | "log"
  | "json"
  | "events"
  | "directive"
  | "diff";

type RawDetailProps = {
  text: string;
  label?: string;
  kind?: RawKind;
  lineNumbers?: boolean;
  /** Lines per page (default keeps the panel responsive). */
  pageSize?: number;
  className?: string;
};

const PAGE_SIZES = [50, 100, 200, 500];

function diffClass(line: string): string {
  if (line.startsWith("@@")) return "text-blue-600 dark:text-blue-400";
  if (line.startsWith("+++") || line.startsWith("---")) return "font-semibold text-neutral-500";
  if (line.startsWith("+")) return "text-emerald-700 dark:text-emerald-400";
  if (line.startsWith("-")) return "text-rose-700 dark:text-rose-400";
  return "";
}

export default function RawDetail({
  text,
  label,
  kind = "text",
  lineNumbers = true,
  pageSize: initialPageSize = 100,
  className = "",
}: RawDetailProps) {
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState("");
  const [copied, setCopied] = useState<"" | "page" | "all">("");

  const allLines = useMemo(() => {
    const normalized = ANSI_KINDS.has(kind) ? stripAnsi(text ?? "") : (text ?? "");
    return normalized.split("\n").map((content, i) => ({ n: i + 1, content }));
  }, [text, kind]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return allLines;
    return allLines.filter((l) => l.content.toLowerCase().includes(q));
  }, [allLines, query]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  // Keep the page in range when the inputs change (stable slices).
  useEffect(() => {
    setPage((p) => Math.min(p, totalPages - 1));
  }, [totalPages]);
  useEffect(() => {
    setPage(0);
  }, [query, pageSize]);

  const safePage = Math.min(page, totalPages - 1);
  const pageLines = filtered.slice(safePage * pageSize, safePage * pageSize + pageSize);
  const isDiff = kind === "diff";

  const copy = async (what: "page" | "all") => {
    const body = what === "all" ? text : pageLines.map((l) => l.content).join("\n");
    try {
      await navigator.clipboard.writeText(body);
      setCopied(what);
      window.setTimeout(() => setCopied(""), 1200);
    } catch {
      /* clipboard blocked — no-op */
    }
  };

  const gutterWidth = `${Math.max(2, String(allLines.length).length)}ch`;

  return (
    <div className={`rounded-md border border-neutral-200 dark:border-neutral-800 ${className}`}>
      {/* controls */}
      <div className="flex flex-wrap items-center gap-1.5 border-b border-neutral-200 px-2 py-1 dark:border-neutral-800">
        {label && <span className="section-title">{label}</span>}
        <span className="font-mono text-[10px] text-neutral-400">
          {query ? `${filtered.length}/${allLines.length}` : allLines.length} ln
        </span>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="filter…"
          aria-label={`Filter ${label ?? "raw"} lines`}
          className="input ml-1 h-6 w-24 px-1.5 py-0 text-[11px]"
        />
        <span className="flex-1" />
        <select
          value={pageSize}
          onChange={(e) => setPageSize(Number(e.target.value))}
          aria-label="Lines per page"
          className="select px-1 py-0.5 text-[10px]"
        >
          {PAGE_SIZES.map((s) => (
            <option key={s} value={s}>
              {s}/pg
            </option>
          ))}
        </select>
        <button className="btn-secondary btn-xs" onClick={() => void copy("page")}>
          {copied === "page" ? "Copied" : "Copy page"}
        </button>
        <button className="btn-secondary btn-xs" onClick={() => void copy("all")}>
          {copied === "all" ? "Copied" : "Copy all"}
        </button>
        <div className="flex items-center gap-0.5">
          <button
            className="icon-btn"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={safePage === 0}
            title="Previous page"
            aria-label="Previous page"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <span className="font-mono text-[10px] tabular-nums text-neutral-400">
            {safePage + 1}/{totalPages}
          </span>
          <button
            className="icon-btn"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={safePage >= totalPages - 1}
            title="Next page"
            aria-label="Next page"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* page body — bounded height, read-only */}
      <div className="max-h-72 overflow-auto bg-neutral-50 font-mono text-[10px] leading-relaxed dark:bg-neutral-950">
        {pageLines.length === 0 ? (
          <p className="px-3 py-2 text-[11px] text-neutral-400">
            {query ? "No matching lines." : "Empty."}
          </p>
        ) : (
          pageLines.map((l) => (
            <div key={l.n} className="flex">
              {lineNumbers && (
                <span
                  className="sticky left-0 select-none border-r border-neutral-200 bg-neutral-100 px-2 text-right text-neutral-400 dark:border-neutral-800 dark:bg-neutral-900"
                  style={{ minWidth: `calc(${gutterWidth} + 1rem)` }}
                  aria-hidden="true"
                >
                  {l.n}
                </span>
              )}
              <span
                className={`whitespace-pre-wrap break-words px-2 text-neutral-700 dark:text-neutral-300 ${isDiff ? diffClass(l.content) : ""}`}
              >
                {l.content || " "}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
