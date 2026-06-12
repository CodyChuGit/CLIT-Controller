import type { TreeNode } from "../types";
import FileTypeIcon from "./FileTypeIcon";
import { ChevronDown, ChevronRight, Folder } from "./icons";

interface NodeProps {
  node: TreeNode;
  depth: number;
  onOpenFile: (path: string) => void;
  selected: string | null;
  expanded: Record<string, boolean>;
  onToggleDir: (path: string, open: boolean) => void;
}

function Node({ node, depth, onOpenFile, selected, expanded, onToggleDir }: NodeProps) {
  // Remembered per workspace; top-level folders start open by default.
  const open = expanded[node.path] ?? depth < 1;
  const pad = { paddingLeft: `${depth * 14 + 8}px` };

  if (node.type === "dir") {
    return (
      <div className="relative">
        <button
          style={pad}
          onClick={() => onToggleDir(node.path, !open)}
          aria-expanded={open}
          className="focusable flex w-full cursor-pointer items-center gap-1.5 rounded py-0.5 pr-2 text-left text-[13px] text-neutral-700 transition-colors duration-150 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
        >
          {open ? (
            <ChevronDown className="h-3 w-3 shrink-0 text-neutral-400" />
          ) : (
            <ChevronRight className="h-3 w-3 shrink-0 text-neutral-400" />
          )}
          <Folder className="h-3.5 w-3.5 shrink-0 text-accent-subtle" />
          <span className="truncate font-medium">{node.name}</span>
        </button>
        {open && (
          <div className="relative">
            {/* VS Code-style indent guide */}
            <span
              aria-hidden="true"
              className="absolute bottom-0 top-0 w-px bg-neutral-200 dark:bg-neutral-800"
              style={{ left: `${depth * 14 + 13}px` }}
            />
            {node.children?.map((c) => (
              <Node
                key={c.path}
                node={c}
                depth={depth + 1}
                onOpenFile={onOpenFile}
                selected={selected}
                expanded={expanded}
                onToggleDir={onToggleDir}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  const previewable = node.previewable !== false;
  return (
    <button
      style={pad}
      disabled={!previewable}
      onClick={() => onOpenFile(node.path)}
      aria-current={selected === node.path ? "true" : undefined}
      title={previewable ? node.path : "Not previewable (binary / excluded)"}
      className={`focusable flex w-full items-center gap-1.5 rounded py-0.5 pr-2 text-left text-[13px] transition-colors duration-150 ${
        selected === node.path
          ? "bg-accent/10 text-blue-700 dark:bg-accent/20 dark:text-blue-300"
          : previewable
            ? "cursor-pointer text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800"
            : "cursor-default text-neutral-400 dark:text-neutral-600"
      }`}
    >
      <span className="w-3 shrink-0" />
      <FileTypeIcon name={node.name} />
      <span className="truncate">{node.name}</span>
    </button>
  );
}

interface Props {
  nodes: TreeNode[];
  onOpenFile: (path: string) => void;
  selected: string | null;
  truncated?: boolean;
  expanded: Record<string, boolean>;
  onToggleDir: (path: string, open: boolean) => void;
}

export default function FileTree({ nodes, onOpenFile, selected, truncated, expanded, onToggleDir }: Props) {
  if (nodes.length === 0) {
    return <p className="p-4 text-sm text-neutral-500 dark:text-neutral-400">Empty folder.</p>;
  }
  return (
    <div className="py-1" role="tree">
      {nodes.map((n) => (
        <Node
          key={n.path}
          node={n}
          depth={0}
          onOpenFile={onOpenFile}
          selected={selected}
          expanded={expanded}
          onToggleDir={onToggleDir}
        />
      ))}
      {truncated && (
        <p className="px-3 py-2 text-[11px] text-neutral-500">Tree truncated (depth 8 / 2000 files max).</p>
      )}
    </div>
  );
}
