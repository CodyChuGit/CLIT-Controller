import type { Health } from "../types";

const OPTIONS: { value: Health; dot: string; active: string }[] = [
  { value: "green", dot: "bg-emerald-500", active: "ring-emerald-500" },
  { value: "yellow", dot: "bg-amber-500", active: "ring-amber-500" },
  { value: "red", dot: "bg-rose-500", active: "ring-rose-500" },
];

interface Props {
  value: Health | null;
  onChange?: (health: Health) => void;
  /** Provider name used in accessible labels, e.g. "claude". */
  name?: string;
}

/** Three clickable dots to set provider usage health manually. */
export default function UsageHealthBadge({ value, onChange, name }: Props) {
  return (
    <div
      className="inline-flex items-center gap-1 rounded-full border border-neutral-200 bg-neutral-50 px-1.5 py-1 dark:border-neutral-700 dark:bg-neutral-800"
      role={onChange ? "radiogroup" : "img"}
      aria-label={`${name ? name + " " : ""}usage health${value ? `: ${value}` : ""}`}
    >
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          role={onChange ? "radio" : undefined}
          aria-checked={onChange ? value === opt.value : undefined}
          aria-label={`Set ${name ?? "provider"} health to ${opt.value}`}
          title={`Set health: ${opt.value}`}
          disabled={!onChange}
          onClick={() => onChange?.(opt.value)}
          className={`focusable h-3.5 w-3.5 rounded-full transition-all duration-150 ${opt.dot} ${
            value === opt.value
              ? `ring-2 ring-offset-1 dark:ring-offset-neutral-800 ${opt.active}`
              : "opacity-30 hover:opacity-70"
          } ${onChange ? "cursor-pointer" : "cursor-default"}`}
        />
      ))}
    </div>
  );
}
