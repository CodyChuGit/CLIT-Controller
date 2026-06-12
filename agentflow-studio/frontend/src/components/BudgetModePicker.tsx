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

export default function BudgetModePicker({ value, onChange }: Props) {
  return (
    <div className="grid grid-cols-2 gap-2 lg:grid-cols-4" role="radiogroup" aria-label="Orchestration mode">
      {MODES.map((m) => (
        <button
          key={m.id}
          role="radio"
          aria-checked={value === m.id}
          onClick={() => onChange(m.id)}
          className={`focusable cursor-pointer rounded-lg border p-3 text-left transition-all duration-150 active:scale-[0.99] ${
            value === m.id
              ? "border-accent bg-blue-50 ring-1 ring-accent dark:border-accent dark:bg-blue-950/40"
              : "border-neutral-200 bg-white hover:border-neutral-300 dark:border-neutral-800 dark:bg-neutral-900 dark:hover:border-neutral-700"
          }`}
        >
          <div className={`text-sm font-medium ${value === m.id ? "text-blue-700 dark:text-blue-300" : ""}`}>
            {m.label}
          </div>
          <div className="mt-0.5 text-[11px] leading-snug text-neutral-500 dark:text-neutral-400">{m.hint}</div>
        </button>
      ))}
    </div>
  );
}
