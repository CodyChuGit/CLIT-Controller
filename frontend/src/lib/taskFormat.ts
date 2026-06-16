/* Presentation layer for the Tasks tab.
 *
 * Raw task events carry a lot of internal noise: every step prompt is prefixed
 * with the identical budget-context header, agent stdout arrives as long
 * unstructured logs, and direct commands are bare shell strings. These pure
 * functions turn that raw text into typed display models the UI can render as
 * compact summaries — the raw text is always preserved on the model so the
 * components can keep it behind a "View raw" disclosure. No data is discarded. */

/* ----------------------------------------------------------------- prompts */

export interface BudgetSummary {
  mode: string | null;
  /** Provider health lines, e.g. { name: "Claude", health: "green" }. */
  providers: { name: string; health: string }[];
  /** The full budget block, verbatim, for the raw disclosure. */
  raw: string;
}

export interface ParsedPrompt {
  budget: BudgetSummary | null;
  /** Task folder the prompt points at, slash stripped (null if absent). */
  taskFolder: string | null;
  /** The actual instruction, with budget + folder boilerplate removed. */
  brief: string;
  /** The untouched prompt. */
  raw: string;
}

const BUDGET_HEADER = "Budget context:";
const BOILERPLATE = "All numbered markdown files mentioned below live in the task folder.";

function parseBudget(block: string): BudgetSummary {
  const modeMatch = block.match(/Current mode:\s*(.+)/);
  const providers: { name: string; health: string }[] = [];
  const re = /-\s*([A-Za-z][\w ]*?) usage:\s*([A-Za-z]+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(block))) providers.push({ name: m[1].trim(), health: m[2].trim() });
  return { mode: modeMatch ? modeMatch[1].trim() : null, providers, raw: block.trim() };
}

/** Split a step prompt into its budget header, task folder, and the real brief.
 *  Falls back gracefully: a prompt without the known header is treated as one
 *  whose entire text is the brief. */
export function parsePrompt(prompt: string): ParsedPrompt {
  const raw = prompt;
  let rest = prompt;
  let budget: BudgetSummary | null = null;

  if (rest.startsWith(BUDGET_HEADER)) {
    const end = rest.indexOf("\n\n");
    const block = end === -1 ? rest : rest.slice(0, end);
    budget = parseBudget(block);
    rest = end === -1 ? "" : rest.slice(end + 2);
  }

  const folderMatch = rest.match(/^Task folder:\s*(\S+)/m);
  const taskFolder = folderMatch ? folderMatch[1].replace(/\/$/, "") : null;

  const brief = rest
    .replace(/^Task folder:.*$/m, "")
    .split("\n")
    .filter((line) => line.trim() !== BOILERPLATE)
    .join("\n")
    .trim();

  return { budget, taskFolder, brief, raw };
}

/** One-line, scannable budget summary, e.g. "Balanced · Claude green · Codex yellow". */
export function summarizeBudget(b: BudgetSummary): string {
  const parts: string[] = [];
  if (b.mode) parts.push(b.mode);
  for (const p of b.providers) parts.push(`${p.name} ${p.health}`);
  return parts.join(" · ") || "Budget context";
}

/* ------------------------------------------------------------------ output */

export interface OutputSummary {
  raw: string;
  empty: boolean;
  lineCount: number;
  errors: string[];
  warnings: string[];
  changedFiles: string[];
  /** Test tally if one was detected, e.g. "12 passed, 1 failed". */
  tests: string | null;
  /** True when the raw output is long enough to warrant collapsing. */
  long: boolean;
}

const ERROR_RE = /\b(error|exception|traceback|fatal|panic|cannot find|not found|failed|failure)\b/i;
const WARN_RE = /\bwarn(ing)?\b/i;
const CHANGED_RE =
  /\b(wrote|created|modified|updated|edited|added|deleted|removed)\b[:\s]+(\S+)/i;
const TEST_RE =
  /(\d+)\s+(?:passed|passing)(?:[^\d]+(\d+)\s+(?:failed|failing))?|(\d+)\s+(?:failed|failing)/i;

function uniq(items: string[], cap: number): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const it of items) {
    const t = it.trim();
    if (!t || seen.has(t)) continue;
    seen.add(t);
    out.push(t);
    if (out.length >= cap) break;
  }
  return out;
}

/** Deterministically summarize agent stdout/log text. No AI involved — just
 *  pattern scanning for the things a person scans for: errors, warnings,
 *  changed files, test results, and the final status line. */
export function summarizeOutput(text: string): OutputSummary {
  const raw = text ?? "";
  const trimmed = raw.trim();
  if (!trimmed) {
    return {
      raw,
      empty: true,
      lineCount: 0,
      errors: [],
      warnings: [],
      changedFiles: [],
      tests: null,
      long: false,
    };
  }

  const lines = trimmed.split("\n");
  const nonEmpty = lines.map((l) => l.trim()).filter(Boolean);

  const errors: string[] = [];
  const warnings: string[] = [];
  const changedFiles: string[] = [];
  let tests: string | null = null;

  for (const line of nonEmpty) {
    if (ERROR_RE.test(line)) errors.push(line);
    else if (WARN_RE.test(line)) warnings.push(line);
    const cm = line.match(CHANGED_RE);
    // Only treat the captured token as a file if it looks like a path
    // (has a "/" or a ".ext") — otherwise "updated the logic" yields "the".
    if (cm && /[/]|\.[a-z0-9]{1,5}$/i.test(cm[2])) {
      changedFiles.push(cm[2].replace(/[.,)]+$/, ""));
    }
    if (!tests) {
      const tm = line.match(TEST_RE);
      if (tm) tests = tm[0].trim();
    }
  }

  return {
    raw,
    empty: false,
    lineCount: lines.length,
    errors: uniq(errors, 5),
    warnings: uniq(warnings, 5),
    changedFiles: uniq(changedFiles, 8),
    tests,
    long: raw.length > 600 || lines.length > 12,
  };
}

/* ---------------------------------------------------------------- commands */

const COMMAND_TITLES: [RegExp, string][] = [
  [/^(npm|yarn|pnpm)\s+(run\s+)?test\b|^pytest\b|^vitest\b|^jest\b|^go\s+test\b/, "Run test suite"],
  [/^(npm|pnpm)\s+(install|i|ci)\b|^yarn(\s+install|\s+add)?\b|^pip\s+install\b/, "Install dependencies"],
  [/^(npm|yarn|pnpm)\s+run\s+build\b|^tsc\b|^vite\s+build\b|^make\b|^cargo\s+build\b/, "Build project"],
  [/^(npm|yarn|pnpm)\s+run\s+dev\b|^vite\b|^next\s+dev\b|^npm\s+start\b/, "Start dev server"],
  [/^(npm|yarn|pnpm)\s+run\s+lint\b|^eslint\b|^ruff\b|^flake8\b/, "Lint code"],
  [/^git\s+status\b/, "Check working tree"],
  [/^git\s+add\b/, "Stage changes"],
  [/^git\s+commit\b/, "Commit changes"],
  [/^git\s+push\b/, "Push to remote"],
  [/^git\s+(pull|fetch)\b/, "Sync with remote"],
  [/^git\s+(diff|show)\b/, "Inspect diff"],
  [/^git\s+(checkout|switch|branch)\b/, "Switch branch"],
  [/^(rg|grep|ag|ack)\b/, "Search codebase"],
  [/^(ls|find|fd|tree)\b/, "List files"],
  [/^(cat|less|head|tail|bat)\b/, "Read file"],
  [/^(mkdir|touch|cp|mv|rm)\b/, "File operation"],
];

/** A human-readable title inferred from a shell command. Strips any leading
 *  path on the binary so "/usr/local/bin/npm test" still matches. */
export function describeCommand(command: string): string {
  const cmd = (command ?? "").trim();
  if (!cmd) return "Run command";
  const tokens = cmd.split(/\s+/);
  const bin = tokens[0].split("/").pop() ?? tokens[0];
  const normalized = [bin, ...tokens.slice(1)].join(" ");
  for (const [re, title] of COMMAND_TITLES) {
    if (re.test(normalized)) return title;
  }
  return `Run ${bin}`;
}

/** Compact human duration: "340ms", "1.2s", "2m 4s". */
export function formatDuration(ms: number | null | undefined): string | null {
  if (ms == null || ms < 0) return null;
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(s < 10 ? 1 : 0)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${Math.round(s % 60)}s`;
}

/** Last one or two path segments of a working directory, for compact display. */
export function shortPath(cwd: string | null | undefined): string | null {
  if (!cwd) return null;
  const parts = cwd.replace(/\/+$/, "").split("/").filter(Boolean);
  if (parts.length <= 2) return cwd;
  return "…/" + parts.slice(-2).join("/");
}
