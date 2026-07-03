import { stripAnsi } from "./ansi";
import { stripResultSentinel } from "./narrative";

/* Live-activity parsing: turn a CLI's raw live output into a structured feed a
   human can follow (what the agent is thinking, which command it just ran, what
   came back) instead of a wall of log text — the same grammar the Codex/Claude
   extensions render. Presentation-only: input is the already-redacted
   accumulated stdout/stderr from the shared event store.

   Ground truth per provider (see docs/cli-interface-mythos-revamp.md):
   - codex exec  → the activity log streams on STDERR (ANSI-marked sections:
     `codex` narration, `thinking`, `exec` + "succeeded in Xms:" results, a
     `user` prompt echo to hide, a `--------` header block); the final answer
     arrives on stdout at the end.
   - claude      → backend stream_normalizer turns stream-json into text with
     `⏺ Tool(summary)` / `  ⎿ first result line` marker lines.
   - antigravity → narrates progressively in plain text; rendered as-is. */

export type ActivityKind = "thinking" | "tool" | "text" | "meta";

export interface ActivityItem {
  kind: ActivityKind;
  /** tool: the command / tool call; meta: the fact line. */
  label?: string;
  /** tool: first line(s) of its output. */
  detail?: string;
  status?: "running" | "ok" | "error";
  /** thinking / narration / answer body. */
  text: string;
}

const TOOL_MARKER = "⏺ ";
const RESULT_MARKER = "⎿";
// codex result line, post-ANSI-strip: " succeeded in 0ms:" / " exited 1 in 2.3s:"
const CODEX_RESULT_RE = /^\s*(succeeded|failed|exited\b.*?) in \d+(?:\.\d+)?\s?m?s:?\s*$/;
const MAX_TOOL_DETAIL_LINES = 2;

/** Unwrap codex's shell wrapper and trailing cwd: `/bin/zsh -lc "cmd" in /dir` → `cmd`. */
function cleanCodexCommand(line: string): string {
  let cmd = line.trim();
  const inIdx = cmd.lastIndexOf(" in /");
  if (inIdx > 0) cmd = cmd.slice(0, inIdx);
  const wrapped = cmd.match(/^\S*sh -lc (["'])([\s\S]*)\1$/);
  if (wrapped) cmd = wrapped[2];
  return cmd;
}

function pushTrimmed(items: ActivityItem[], current: ActivityItem | null): null {
  if (current) {
    current.text = current.text.replace(/\s+$/, "");
    if (current.kind === "tool" || current.text || current.label) items.push(current);
  }
  return null;
}

/** codex exec's stderr activity log → items. */
function parseCodexStderr(stderr: string): ActivityItem[] {
  const items: ActivityItem[] = [];
  let current: ActivityItem | null = null;
  let section: "preamble" | "header" | "user" | "body" = "preamble";
  let expectCommand = false;
  let detailLines = 0;

  for (const raw of stripAnsi(stderr).split("\n")) {
    const line = raw.trimEnd();
    const t = line.trim();
    if (t === "--------") {
      section = section === "header" ? "body" : "header";
      continue;
    }
    if (section === "header") {
      if (t.startsWith("model:")) items.push({ kind: "meta", text: t });
      continue;
    }
    if (t === "user") {
      current = pushTrimmed(items, current);
      section = "user"; // echoed prompt — never show it as activity
      continue;
    }
    if (t === "codex") {
      current = pushTrimmed(items, current);
      section = "body";
      current = { kind: "text", text: "" };
      continue;
    }
    if (t === "thinking") {
      current = pushTrimmed(items, current);
      section = "body";
      current = { kind: "thinking", text: "" };
      continue;
    }
    if (t === "exec") {
      current = pushTrimmed(items, current);
      section = "body";
      current = { kind: "tool", label: "", status: "running", text: "" };
      expectCommand = true;
      continue;
    }
    if (/^tokens used:/i.test(t)) {
      current = pushTrimmed(items, current);
      items.push({ kind: "meta", text: t });
      continue;
    }
    if (section === "user" || section === "preamble") continue;
    if (expectCommand && current) {
      current.label = cleanCodexCommand(line);
      expectCommand = false;
      continue;
    }
    if (current?.kind === "tool" && current.status === "running" && CODEX_RESULT_RE.test(line)) {
      current.status = /succeeded/.test(line) ? "ok" : "error";
      detailLines = 0;
      continue;
    }
    if (current?.kind === "tool") {
      // lines after the result line are the command's output — keep a taste
      if (current.status !== "running" && t && detailLines < MAX_TOOL_DETAIL_LINES) {
        current.detail = current.detail ? `${current.detail}\n${t}` : t;
        detailLines++;
      }
      continue;
    }
    if (current) current.text += `${raw}\n`;
  }
  pushTrimmed(items, current);
  return items;
}

/** ⏺/⎿-marked (claude, via the backend normalizer) or plain narration text → items. */
function parseMarkedText(stdout: string): ActivityItem[] {
  const items: ActivityItem[] = [];
  let current: ActivityItem | null = null;
  let lastTool: ActivityItem | null = null;

  for (const raw of stripAnsi(stripResultSentinel(stdout)).split("\n")) {
    if (raw.startsWith(TOOL_MARKER)) {
      current = pushTrimmed(items, current);
      lastTool = { kind: "tool", label: raw.slice(TOOL_MARKER.length).trim(), status: "running", text: "" };
      items.push(lastTool);
      continue;
    }
    const t = raw.trim();
    if (t.startsWith(RESULT_MARKER)) {
      if (lastTool) {
        const detail = t.slice(RESULT_MARKER.length).trim();
        lastTool.detail = detail;
        lastTool.status = detail.startsWith("error") ? "error" : "ok";
      }
      continue;
    }
    if (!current) current = { kind: "text", text: "" };
    current.text += `${raw}\n`;
  }
  pushTrimmed(items, current);
  return items;
}

/** The live-activity feed for one run. `provider` picks the dialect. */
export function parseLiveActivity(
  provider: string | null | undefined,
  stdout: string,
  stderr: string,
): ActivityItem[] {
  let items: ActivityItem[];
  if (provider === "codex") {
    items = parseCodexStderr(stderr);
    const answer = stripResultSentinel(stripAnsi(stdout)).trim();
    if (answer) items.push({ kind: "text", text: answer });
  } else {
    items = parseMarkedText(stdout);
    // Nothing on stdout but stderr is talking (auth errors, crashes) — show it.
    if (items.length === 0 && stderr.trim()) {
      const tail = stripAnsi(stderr).trim().split("\n").slice(-4).join("\n");
      items = [{ kind: "meta", text: tail }];
    }
  }
  return items;
}
