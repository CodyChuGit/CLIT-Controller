import type { EditorFile } from "../types";
import { FileIcon } from "./icons";

const MAX_GUTTER_LINES = 8000; // skip line numbers on huge files

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

  const lines = file.content.split("\n");
  const showGutter = lines.length <= MAX_GUTTER_LINES;
  const gutterWidth = `${Math.max(String(lines.length).length, 2)}ch`;

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
          <pre className="flex-1 whitespace-pre px-4 py-3 text-neutral-800 dark:text-neutral-200">
            {file.content}
          </pre>
        </div>
      </div>
    </div>
  );
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
