interface Props {
  path: string | null;
  content: string | null;
  size?: number;
  truncated?: boolean;
  error?: string | null;
}

function formatSize(bytes?: number): string {
  if (bytes === undefined) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function CodeReader({ path, content, size, truncated, error }: Props) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-neutral-200 px-4 py-2.5 dark:border-neutral-800">
        <span className="truncate font-mono text-xs text-neutral-600 dark:text-neutral-400">
          {path ?? "Select a file"}
        </span>
        <span className="shrink-0 text-[11px] text-neutral-400">
          {formatSize(size)}
          {truncated && " · truncated at 512 KB"}
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {error ? (
          <p className="p-4 text-sm text-rose-500">{error}</p>
        ) : content === null ? (
          <p className="p-4 text-sm text-neutral-400">Click a file in the tree to read it.</p>
        ) : (
          <pre className="p-4 font-mono text-xs leading-relaxed text-neutral-800 dark:text-neutral-200">
            {content}
          </pre>
        )}
      </div>
    </div>
  );
}
