import { useMemo } from "react";
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
import { FileIcon } from "./icons";

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

/** Read-only editor pane with a sticky line-number gutter (VS Code-style). */
export default function CodeReader({ file }: { file: EditorFile | null }) {
  if (!file) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 bg-white text-center dark:bg-neutral-900">
        <FileIcon className="h-7 w-7 text-neutral-300 dark:text-neutral-600" />
        <p className="text-sm text-neutral-500">Open a file from the Explorer to read it.</p>
        <p className="text-xs text-neutral-400">Files open as tabs. The beta editor is read-only.</p>
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

  return <FileView file={file} />;
}

function FileView({ file }: { file: EditorFile }) {
  const content = file.content ?? "";
  const lines = content.split("\n");
  const showGutter = lines.length <= MAX_GUTTER_LINES;
  const gutterWidth = `${Math.max(String(lines.length).length, 2)}ch`;

  // VS Code-style syntax coloring (token palette in styles.css).
  const highlighted = useMemo(() => {
    if (file.kind === "diff" || !showGutter) return null;
    const ext = file.path.split(".").pop()?.toLowerCase() ?? "";
    const lang = LANG_BY_EXT[ext];
    const grammar = lang ? Prism.languages[lang] : undefined;
    if (!grammar) return null;
    try {
      return Prism.highlight(content, grammar, lang);
    } catch {
      return null;
    }
  }, [content, file.path, file.kind, showGutter]);

  return (
    <div className="flex h-full flex-col bg-white dark:bg-neutral-900">
      <Breadcrumb file={file} />
      <div className="min-h-0 flex-1 overflow-auto">
        <div className="flex min-w-full font-mono text-xs leading-5">
          {showGutter && (
            <pre
              aria-hidden="true"
              className="sticky left-0 z-10 select-none border-r border-neutral-200 bg-neutral-50 px-3 py-3 text-right text-neutral-400 dark:border-neutral-800 dark:bg-neutral-950 dark:text-neutral-600"
              style={{ minWidth: `calc(${gutterWidth} + 1.5rem)` }}
            >
              {lines.map((_, i) => i + 1).join("\n")}
            </pre>
          )}
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
            <pre className="flex-1 whitespace-pre px-4 py-3 text-neutral-800 dark:text-neutral-200">{content}</pre>
          )}
        </div>
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

function Breadcrumb({ file }: { file: EditorFile }) {
  return (
    <div className="flex shrink-0 items-center justify-between gap-2 border-b border-neutral-200 px-4 py-1.5 dark:border-neutral-800">
      <span className="truncate font-mono text-[11px] text-neutral-500 dark:text-neutral-400" title={file.path}>
        {file.path.split("/").join(" › ")}
      </span>
      <span className="shrink-0 text-[11px] tabular-nums text-neutral-400">
        {formatSize(file.size)}
        {file.truncated && " · truncated at 512 KB"}
      </span>
    </div>
  );
}
