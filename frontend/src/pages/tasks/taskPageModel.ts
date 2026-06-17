import { parsePrompt, type BudgetSummary } from "../../lib/taskFormat";
import type { CardModel, CardType } from "../../lib/displayModel";
import type { Exchange, RunInfo, TaskDetail } from "../../types";

export const STEP_ORDER = ["codex_spec", "claude_implement", "gemini_qa", "codex_review", "claude_fix"];

export const SHORT_LABELS: Record<string, string> = {
  codex_spec: "Spec",
  claude_implement: "Implement",
  gemini_qa: "QA",
  codex_review: "Review",
  claude_fix: "Fix",
};

export const QUEUE_ACTIVE = ["queued", "awaiting_approval", "blocked", "running"];

export function collectBudgetContext(
  exchanges: Record<string, Exchange[]>,
): { budget: BudgetSummary; repeated: number } | null {
  const all: BudgetSummary[] = [];
  for (const list of Object.values(exchanges)) {
    for (const ex of list) {
      const budget = parsePrompt(ex.prompt).budget;
      if (budget) all.push(budget);
    }
  }
  if (all.length === 0) return null;
  return { budget: all[all.length - 1], repeated: all.length };
}

export function taskCommandRuns(detail: TaskDetail | null): RunInfo[] {
  return (detail?.runs ?? []).filter((run) => run.step === "run" || run.provider === "shell");
}

export function taskChangedFiles(detail: TaskDetail | null): string[] {
  if (!detail) return [];
  return Array.from(new Set(Object.values(detail.task.steps).flatMap((step) => step.codeChanged ?? [])));
}

export function buildFinalCard(detail: TaskDetail | null): CardModel | null {
  if (!detail) return null;
  const status = detail.task.status;
  if (!["done", "failed", "needs_user", "cancelled", "abandoned"].includes(status)) return null;

  const events = detail.task.events ?? [];
  const verdict = [...events].reverse().find((event) => ["done", "needs_user"].includes(event.type));
  const changed = new Set<string>();
  Object.values(detail.task.steps).forEach((step) => (step.codeChanged ?? []).forEach((file) => changed.add(file)));
  const stepsRun = Object.values(detail.task.steps).filter((step) => step.status && step.status !== "idle").length;
  const isDone = status === "done";
  const type: CardType = isDone ? "FINAL_SUMMARY" : status === "needs_user" ? "NEEDS_USER" : "FAILURE";
  const bullets: string[] = [];
  if (verdict?.detail) bullets.push(verdict.detail);
  bullets.push(`${stepsRun} step${stepsRun === 1 ? "" : "s"} run`);
  if (changed.size) bullets.push(`${changed.size} file${changed.size === 1 ? "" : "s"} changed`);

  return {
    id: `final-${detail.task.id}`,
    type,
    action: { taskId: detail.task.id, stateTo: status },
    display: {
      cardType: type,
      title: isDone ? "Task complete" : status === "needs_user" ? "Needs your input" : `Task ${status}`,
      severity: isDone ? "ok" : status === "needs_user" ? "warn" : "error",
      taskId: detail.task.id,
      summary: { title: "Final report", bullets: bullets.slice(0, 5) },
      artifacts: [...changed].slice(0, 8),
    },
  };
}

export function taskFileKind(name: string): "json" | "log" | "diff" | "text" {
  if (name.endsWith(".json")) return "json";
  if (name.endsWith(".log")) return "log";
  if (name.endsWith(".diff") || name.endsWith(".patch")) return "diff";
  return "text";
}
