import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import Prism from "prismjs";
import "prismjs/components/prism-markup";
import "prismjs/components/prism-css";
import "prismjs/components/prism-clike";
import "prismjs/components/prism-javascript";
import "prismjs/components/prism-typescript";
import "prismjs/components/prism-jsx";
import "prismjs/components/prism-tsx";
import "prismjs/components/prism-python";
import "prismjs/components/prism-json";
import "prismjs/components/prism-bash";
import "prismjs/components/prism-swift";
import "prismjs/components/prism-yaml";
import "prismjs/components/prism-markdown";
import "prismjs/components/prism-rust";
import "prismjs/components/prism-go";
import "prismjs/components/prism-java";
import "prismjs/components/prism-kotlin";
import "prismjs/components/prism-c";
import "prismjs/components/prism-cpp";
import "prismjs/components/prism-toml";
import type { EditorFile } from "../types";
import { FileIcon, Spinner } from "./icons";

interface EditorProps {
  file: EditorFile | null;
  /** Unsaved edit for the active file (lives in App so it survives tab switches). */
  draft?: string;
  onDraftChange?: (path: string, content: string) => void;
  onSave?: (path: string, content: string) => Promise<void>;
}

const MAX_GUTTER_LINES = 8000; // skip line numbers (and highlighting) on huge files

const LANG_BY_EXT: Record<string, string> = {
  ts: "typescript",
  tsx: "tsx",
  js: "javascript",
  jsx: "jsx",
  mjs: "javascript",
  py: "python",
  json: "json",
  css: "css",
  html: "markup",
  xml: "markup",
  svg: "markup",
  sh: "bash",
  zsh: "bash",
  swift: "swift",
  yml: "yaml",
  yaml: "yaml",
  md: "markdown",
  rs: "rust",
  go: "go",
  java: "java",
  kt: "kotlin",
  c: "c",
  h: "c",
  cpp: "cpp",
  hpp: "cpp",
  toml: "toml",
};

function formatSize(bytes?: number): string {
  if (bytes === undefined) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Editor pane with a sticky line-number gutter (VS Code-style). Text files are
    editable with save; diffs and truncated/binary files stay read-only. */
export default function CodeReader({ file, draft, onDraftChange, onSave }: EditorProps) {
  if (!file) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 bg-white text-center dark:bg-neutral-900">
        <FileIcon className="h-7 w-7 text-neutral-300 dark:text-neutral-600" />
        <p className="text-sm text-neutral-500">Open a file from the Explorer to read it.</p>
        <p className="text-xs text-neutral-400">Files open as tabs. Click Edit to make changes and save.</p>
      </div>
    );
  }

  if (file.error || file.content === null) {
    return (
      <div className="flex h-full flex-col bg-white dark:bg-neutral-900">
        <Breadcrumb file={file} />
        <p className="p-4 text-sm text-rose-600 dark:text-rose-400" role="alert">
          {file.error ?? "Could not read this file."}
        </p>
      </div>
    );
  }

  return <FileView key={file.path} file={file} draft={draft} onDraftChange={onDraftChange} onSave={onSave} />;
}

function FileView({
  file,
  draft,
  onDraftChange,
  onSave,
}: {
  file: EditorFile;
  draft?: string;
  onDraftChange?: (path: string, content: string) => void;
  onSave?: (path: string, content: string) => Promise<void>;
}) {
  const saved = file.content ?? "";
  // The text currently shown/edited: the unsaved draft if any, else saved content.
  const value = draft ?? saved;
  const dirty = draft !== undefined && draft !== saved;

  // Diffs are read-only; truncated files only hold a partial head, so saving
  // them would clobber the rest — keep those read-only too.
  const editable = file.kind !== "diff" && !file.truncated && Boolean(onSave && onDraftChange);

  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const lines = value.split("\n");
  const showGutter = lines.length <= MAX_GUTTER_LINES;
  const gutterWidth = `${Math.max(String(lines.length).length, 2)}ch`;

  // VS Code-style syntax coloring (token palette in styles.css). Recomputed from
  // `value` so an unsaved draft still highlights in read mode.
  const highlighted = useMemo(() => {
    if (file.kind === "diff" || !showGutter) return null;
    const ext = file.path.split(".").pop()?.toLowerCase() ?? "";
    const lang = LANG_BY_EXT[ext];
    const grammar = lang ? Prism.languages[lang] : undefined;
    if (!grammar) return null;
    try {
      return Prism.highlight(value, grammar, lang);
    } catch {
      return null;
    }
  }, [value, file.path, file.kind, showGutter]);

  const save = async () => {
    if (!editable || !dirty || saving || !onSave) return;
    setSaving(true);
    setSaveError(null);
    try {
      await onSave(file.path, value);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex h-full flex-col bg-white dark:bg-neutral-900">
      <Breadcrumb file={file}>
        {editable &&
          (editing ? (
            <>
              <button className="btn-secondary btn-xs" onClick={() => setEditing(false)}>
                Done
              </button>
              <button className="btn-primary btn-xs" onClick={() => void save()} disabled={!dirty || saving}>
                {saving && <Spinner className="h-3 w-3" />}
                {saving ? "Saving…" : "Save"}
              </button>
            </>
          ) : (
            <button className="btn-secondary btn-xs" onClick={() => setEditing(true)}>
              Edit
            </button>
          ))}
      </Breadcrumb>
      {saveError && (
        <p className="shrink-0 border-b border-rose-200 bg-rose-50 px-4 py-1.5 text-[11px] text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300" role="alert">
          {saveError}
        </p>
      )}
      {editing ? (
        <Editor
          value={value}
          lines={lines}
          showGutter={showGutter}
          gutterWidth={gutterWidth}
          onChange={(next) => onDraftChange?.(file.path, next)}
          onSave={() => void save()}
        />
      ) : (
        <div className="min-h-0 flex-1 overflow-auto">
          <div className="flex min-w-full font-mono text-xs leading-5">
            {showGutter && <Gutter lineCount={lines.length} gutterWidth={gutterWidth} />}
            {file.kind === "diff" ? (
              <pre className="flex-1 whitespace-pre px-4 py-3">
                {lines.map((line, i) => (
                  <span key={i} className={diffLineClass(line)}>
                    {line}
                    {"\n"}
                  </span>
                ))}
              </pre>
            ) : highlighted !== null ? (
              <pre className="code-highlight flex-1 whitespace-pre px-4 py-3 text-neutral-800 dark:text-neutral-200">
                <code dangerouslySetInnerHTML={{ __html: highlighted }} />
              </pre>
            ) : (
              <pre className="flex-1 whitespace-pre px-4 py-3 text-neutral-800 dark:text-neutral-200">{value}</pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Gutter({ lineCount, gutterWidth }: { lineCount: number; gutterWidth: string }) {
  return (
    <pre
      aria-hidden="true"
      className="sticky left-0 z-10 select-none border-r border-neutral-200 bg-neutral-50 px-3 py-3 text-right text-neutral-400 dark:border-neutral-800 dark:bg-neutral-950 dark:text-neutral-600"
      style={{ minWidth: `calc(${gutterWidth} + 1.5rem)` }}
    >
      {Array.from({ length: lineCount }, (_, i) => i + 1).join("\n")}
    </pre>
  );
}

/** Plain <textarea> editor sharing the read view's gutter + mono metrics. The
    textarea auto-grows to its content so gutter and text scroll together. */
function Editor({
  value,
  lines,
  showGutter,
  gutterWidth,
  onChange,
  onSave,
}: {
  value: string;
  lines: string[];
  showGutter: boolean;
  gutterWidth: string;
  onChange: (next: string) => void;
  onSave: () => void;
}) {
  const ref = useRef<HTMLTextAreaElement | null>(null);

  // Grow the textarea to fit its content (no internal scrollbar) so the shared
  // outer scroll container keeps the gutter aligned with the text.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  useEffect(() => {
    ref.current?.focus();
  }, []);

  return (
    <div className="min-h-0 flex-1 overflow-auto">
      <div className="flex min-w-full font-mono text-xs leading-5">
        {showGutter && <Gutter lineCount={lines.length} gutterWidth={gutterWidth} />}
        <textarea
          ref={ref}
          value={value}
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
          wrap="off"
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
              e.preventDefault();
              onSave();
            }
          }}
          className="flex-1 resize-none whitespace-pre bg-transparent px-4 py-3 font-mono text-xs leading-5 text-neutral-800 outline-none dark:text-neutral-200"
          aria-label="File contents"
        />
      </div>
    </div>
  );
}

function diffLineClass(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("diff ")) {
    return "font-semibold text-neutral-500 dark:text-neutral-400";
  }
  if (line.startsWith("@@")) return "text-blue-600 dark:text-blue-400";
  if (line.startsWith("+")) return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400";
  if (line.startsWith("-")) return "bg-rose-500/10 text-rose-700 dark:text-rose-400";
  return "text-neutral-700 dark:text-neutral-300";
}

function Breadcrumb({ file, children }: { file: EditorFile; children?: ReactNode }) {
  return (
    <div className="flex shrink-0 items-center gap-2 border-b border-neutral-200 px-4 py-1.5 dark:border-neutral-800">
      <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-neutral-500 dark:text-neutral-400" title={file.path}>
        {file.path.split("/").join(" › ")}
      </span>
      <span className="shrink-0 text-[11px] tabular-nums text-neutral-400">
        {formatSize(file.size)}
        {file.truncated && " · truncated at 512 KB"}
      </span>
      {children}
    </div>
  );
}
