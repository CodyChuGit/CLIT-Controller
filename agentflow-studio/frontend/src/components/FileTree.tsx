import { useState } from "react";
import type { TreeNode } from "../types";

interface NodeProps {
  node: TreeNode;
  depth: number;
  onOpenFile: (path: string) => void;
  selected: string | null;
}

function Node({ node, depth, onOpenFile, selected }: NodeProps) {
  const [open, setOpen] = useState(depth < 1);
  const pad = { paddingLeft: `${depth * 14 + 8}px` };

  if (node.type === "dir") {
    return (
      <div>
        <button
          style={pad}
          onClick={() => setOpen(!open)}
          className="flex w-full items-center gap-1.5 rounded py-1 pr-2 text-left text-[13px] text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
        >
          <span className="w-3 text-[10px] text-neutral-400">{open ? "▾" : "▸"}</span>
          <span className="text-blue-500">▣</span>
          <span className="truncate font-medium">{node.name}</span>
        </button>
        {open && node.children?.map((c) => (
          <Node key={c.path} node={c} depth={depth + 1} onOpenFile={onOpenFile} selected={selected} />
        ))}
      </div>
    );
  }

  const previewable = node.previewable !== false;
  return (
    <button
      style={pad}
      disabled={!previewable}
      onClick={() => onOpenFile(node.path)}
      title={previewable ? node.path : "Not previewable (binary / excluded)"}
      className={`flex w-full items-center gap-1.5 rounded py-1 pr-2 text-left text-[13px] ${
        selected === node.path
          ? "bg-blue-600/10 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300"
          : previewable
            ? "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-400 dark:hover:bg-neutral-800"
            : "cursor-default text-neutral-400 dark:text-neutral-600"
      }`}
    >
      <span className="w-3" />
      <span className="text-neutral-400">▢</span>
      <span className="truncate">{node.name}</span>
    </button>
  );
}

interface Props {
  nodes: TreeNode[];
  onOpenFile: (path: string) => void;
  selected: string | null;
  truncated?: boolean;
}

export default function FileTree({ nodes, onOpenFile, selected, truncated }: Props) {
  if (nodes.length === 0) {
    return <p className="p-4 text-sm text-neutral-400">Empty folder.</p>;
  }
  return (
    <div className="py-1">
      {nodes.map((n) => (
        <Node key={n.path} node={n} depth={0} onOpenFile={onOpenFile} selected={selected} />
      ))}
      {truncated && (
        <p className="px-3 py-2 text-[11px] text-neutral-400">Tree truncated (depth 8 / 2000 files max).</p>
      )}
    </div>
  );
}
