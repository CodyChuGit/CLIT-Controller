import { useEffect, useMemo, useRef, useState } from "react";

export interface PaletteAction {
  id: string;
  label: string;
  /** Right-aligned mono hint (provider id, task id, shortcut…). */
  hint?: string;
  disabled?: boolean;
  run: () => void;
}

/** A VS Code-style command palette scoped to CLITC-native actions only — no
 *  vscode:// links, no extension commands. Filterable list over a dim backdrop;
 *  Enter runs the top match, Esc closes. */
export default function CommandPalette({
  open,
  onClose,
  actions,
}: {
  open: boolean;
  onClose: () => void;
  actions: PaletteAction[];
}) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      // focus after the element mounts
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const enabled = actions.filter((a) => !a.disabled);
    if (!q) return enabled;
    return enabled.filter((a) => `${a.label} ${a.hint ?? ""}`.toLowerCase().includes(q));
  }, [actions, query]);

  if (!open) return null;

  const run = (a: PaletteAction | undefined) => {
    if (!a) return;
    onClose();
    a.run();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 pt-[12vh]"
      onMouseDown={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div
        className="w-[min(32rem,90vw)] overflow-hidden rounded-lg border border-neutral-300 bg-white shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            else if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((i) => Math.min(matches.length - 1, i + 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((i) => Math.max(0, i - 1));
            } else if (e.key === "Enter") {
              e.preventDefault();
              run(matches[active]);
            }
          }}
          placeholder="Run a CLITC action…"
          aria-label="Command palette filter"
          className="w-full border-b border-neutral-200 bg-white px-3 py-2.5 text-sm text-neutral-900 outline-none placeholder:text-neutral-400 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-100"
        />
        <div className="max-h-72 overflow-y-auto py-1">
          {matches.length === 0 ? (
            <p className="px-3 py-3 text-xs text-neutral-400">No matching actions.</p>
          ) : (
            matches.map((a, i) => (
              <button
                key={a.id}
                onMouseEnter={() => setActive(i)}
                onClick={() => run(a)}
                className={`flex w-full cursor-pointer items-center gap-2 px-3 py-1.5 text-left text-xs transition-colors ${
                  i === active
                    ? "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300"
                    : "text-neutral-700 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
                }`}
              >
                <span className="min-w-0 flex-1 truncate">{a.label}</span>
                {a.hint && <span className="shrink-0 font-mono text-[10px] text-neutral-400">{a.hint}</span>}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
