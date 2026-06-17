const SPECIAL_ARTIFACTS: Record<string, string> = {
  "@code": "production code",
  "@diff": "git diff",
  "@folder": "task folder",
};

export default function ArtifactChip({ name, onOpen }: { name: string; onOpen?: (name: string) => void }) {
  const special = SPECIAL_ARTIFACTS[name];
  if (special) {
    return (
      <span className="rounded border border-violet-200 bg-violet-50 px-1.5 py-0.5 font-mono text-[10px] text-violet-700 dark:border-violet-900 dark:bg-violet-950/40 dark:text-violet-300">
        {special}
      </span>
    );
  }
  return (
    <button
      onClick={() => onOpen?.(name)}
      disabled={!onOpen}
      title={onOpen ? `Open ${name}` : name}
      className={`focusable rounded border border-emerald-300 bg-emerald-50 px-1.5 py-0.5 font-mono text-[10px] text-emerald-700 transition-colors dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 ${
        onOpen ? "cursor-pointer hover:border-blue-400 hover:text-blue-600 dark:hover:text-blue-300" : ""
      }`}
    >
      {name.replace(".md", "")}
    </button>
  );
}
