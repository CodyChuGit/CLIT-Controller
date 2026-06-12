import { FileIcon } from "./icons";

/** VS Code-style letter badges per file type (see DESIGN.md › file-type icons). */
const EXT_BADGES: Record<string, { label: string; cls: string }> = {
  ts: { label: "TS", cls: "bg-blue-600 text-white" },
  tsx: { label: "TX", cls: "bg-blue-500 text-white" },
  js: { label: "JS", cls: "bg-yellow-400 text-yellow-950" },
  jsx: { label: "JX", cls: "bg-yellow-500 text-yellow-950" },
  py: { label: "PY", cls: "bg-sky-600 text-white" },
  json: { label: "{}", cls: "bg-amber-500 text-amber-950" },
  md: { label: "MD", cls: "bg-sky-500 text-white" },
  html: { label: "<>", cls: "bg-orange-600 text-white" },
  css: { label: "#", cls: "bg-indigo-500 text-white" },
  sh: { label: "$_", cls: "bg-neutral-600 text-white" },
  yml: { label: "Y", cls: "bg-purple-500 text-white" },
  yaml: { label: "Y", cls: "bg-purple-500 text-white" },
  toml: { label: "T", cls: "bg-stone-500 text-white" },
  swift: { label: "SW", cls: "bg-orange-500 text-white" },
  rs: { label: "RS", cls: "bg-orange-700 text-white" },
  go: { label: "GO", cls: "bg-cyan-600 text-white" },
  java: { label: "J", cls: "bg-red-600 text-white" },
  kt: { label: "KT", cls: "bg-violet-600 text-white" },
  c: { label: "C", cls: "bg-blue-700 text-white" },
  cpp: { label: "C+", cls: "bg-blue-800 text-white" },
  h: { label: "H", cls: "bg-slate-600 text-white" },
  hpp: { label: "H+", cls: "bg-slate-700 text-white" },
  txt: { label: "≡", cls: "bg-neutral-500 text-white" },
  svg: { label: "SVG", cls: "bg-teal-600 text-white" },
};

// Special filenames take precedence over extensions.
const NAME_BADGES: Record<string, { label: string; cls: string }> = {
  ".gitignore": { label: "GIT", cls: "bg-orange-700 text-white" },
  ".env.example": { label: "ENV", cls: "bg-lime-600 text-white" },
  Dockerfile: { label: "DOC", cls: "bg-sky-700 text-white" },
  Makefile: { label: "MK", cls: "bg-stone-600 text-white" },
};

export default function FileTypeIcon({ name, className = "" }: { name: string; className?: string }) {
  const badge = NAME_BADGES[name] ?? EXT_BADGES[name.split(".").pop()?.toLowerCase() ?? ""];
  if (!badge) {
    return <FileIcon className={`h-3.5 w-3.5 shrink-0 text-neutral-400 ${className}`} />;
  }
  return (
    <span
      aria-hidden="true"
      className={`flex h-3.5 w-3.5 shrink-0 select-none items-center justify-center rounded-[3px] text-[7px] font-bold leading-none ${badge.cls} ${className}`}
    >
      {badge.label}
    </span>
  );
}
