import type { OrchestrationMode } from "../types";

const MODES: { id: OrchestrationMode; label: string; hint: string }[] = [
  { id: "maximum_quality", label: "Maximum Quality", hint: "Full chain incl. final review" },
  { id: "balanced", label: "Balanced", hint: "Standard chain, conserve yellow providers" },
  { id: "budget_saver", label: "Budget Saver", hint: "Skip spec on small tasks, local first" },
  { id: "manual_approval", label: "Manual Approval", hint: "Previews only — you run each step" },
];

interface Props {
  value: OrchestrationMode;
  onChange: (mode: OrchestrationMode) => void;
}

/** Segmented control; hints live in tooltips to keep the row quiet. */
export default function BudgetModePicker({ value, onChange }: Props) {
  return (
    <div
      className="inline-flex overflow-hidden rounded-md border border-neutral-200 dark:border-neutral-800"
      role="radiogroup"
      aria-label="Traffic control mode"
    >
      {MODES.map((m) => (
        <button
          key={m.id}
          role="radio"
          aria-checked={value === m.id}
          title={m.hint}
          onClick={() => onChange(m.id)}
          className={`focusable cursor-pointer border-l border-neutral-200 px-3 py-1 text-xs transition-colors duration-150 first:border-l-0 dark:border-neutral-800 ${
            value === m.id
              ? "bg-blue-50 font-medium text-blue-700 dark:bg-blue-950/40 dark:text-blue-300"
              : "bg-white text-neutral-500 hover:bg-neutral-50 hover:text-neutral-700 dark:bg-neutral-900 dark:text-neutral-400 dark:hover:bg-neutral-800 dark:hover:text-neutral-200"
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
