import { describe, expect, it } from "vitest";
import { parseLiveActivity } from "./liveActivity";

/* The codex sample reproduces a real `codex exec` stderr capture (ANSI-marked
   sections, header block, prompt echo, exec results); the claude sample is the
   backend stream_normalizer's marker grammar. */

const ESC = "\u001b";
const CODEX_STDERR = [
  "Reading additional input from stdin...",
  "OpenAI Codex v0.139.0",
  "--------",
  `${ESC}[1mworkdir:${ESC}[0m /Users/cody/TestApp`,
  `${ESC}[1mmodel:${ESC}[0m gpt-5.5`,
  `${ESC}[1mapproval:${ESC}[0m never`,
  "--------",
  `${ESC}[36muser${ESC}[0m`,
  "Budget context:",
  "- Current mode: Balanced",
  "Read the goal file and write the spec.",
  `${ESC}[35m${ESC}[3mcodex${ESC}[0m${ESC}[0m`,
  "I'll read the goal file and the task folder shape, then write the two files.",
  `${ESC}[35m${ESC}[3mexec${ESC}[0m${ESC}[0m`,
  `${ESC}[1m/bin/zsh -lc "sed -n '1,220p' 00_USER_GOAL.md"${ESC}[0m in /Users/cody/TestApp`,
  `${ESC}[32m succeeded in 0ms:${ESC}[0m`,
  "# User Goal",
  "",
  "## Setup React Node.js Environment",
  `${ESC}[35m${ESC}[3mexec${ESC}[0m${ESC}[0m`,
  `${ESC}[1m/bin/zsh -lc "rm -rf /nope"${ESC}[0m in /Users/cody/TestApp`,
  `${ESC}[31m exited 1 in 12ms:${ESC}[0m`,
  "permission denied",
].join("\n");

describe("parseLiveActivity — codex (activity on stderr)", () => {
  const items = parseLiveActivity("codex", "", CODEX_STDERR);

  it("hides the prompt echo and preamble, keeps model as meta", () => {
    const text = items.map((i) => `${i.label ?? ""}${i.text}`).join("\n");
    expect(text).not.toContain("Budget context");
    expect(text).not.toContain("Reading additional input");
    expect(items.some((i) => i.kind === "meta" && i.text.includes("gpt-5.5"))).toBe(true);
  });

  it("captures narration and exec commands with status + output taste", () => {
    const narration = items.find((i) => i.kind === "text");
    expect(narration?.text).toContain("I'll read the goal file");

    const tools = items.filter((i) => i.kind === "tool");
    expect(tools).toHaveLength(2);
    expect(tools[0].label).toBe("sed -n '1,220p' 00_USER_GOAL.md"); // shell wrapper + cwd stripped
    expect(tools[0].status).toBe("ok");
    expect(tools[0].detail).toContain("# User Goal");
    expect(tools[1].status).toBe("error");
    expect(tools[1].detail).toContain("permission denied");
  });

  it("appends the stdout final answer as the last text item, sentinel stripped", () => {
    const withAnswer = parseLiveActivity(
      "codex",
      "Spec written.\n\n<<<CLITC_RESULT_V1\n{}\nCLITC_RESULT_V1>>>\n",
      CODEX_STDERR,
    );
    const last = withAnswer[withAnswer.length - 1];
    expect(last.kind).toBe("text");
    expect(last.text).toBe("Spec written.");
  });
});

describe("parseLiveActivity — claude (normalized ⏺/⎿ markers)", () => {
  const STDOUT = [
    "I'll check the failing test first.",
    "⏺ Bash(npm test -- --run auth)",
    "  ⎿ 3 passed, 1 failed",
    "⏺ Edit(src/auth.ts)",
    "  ⎿ error: file busy",
    "The fix is in place. Done.",
  ].join("\n");
  const items = parseLiveActivity("claude", STDOUT, "");

  it("splits narration around tool calls in order", () => {
    expect(items.map((i) => i.kind)).toEqual(["text", "tool", "tool", "text"]);
    expect(items[0].text).toContain("check the failing test");
    expect(items[3].text).toContain("Done.");
  });

  it("attaches result lines and error status to the owning tool", () => {
    expect(items[1].label).toBe("Bash(npm test -- --run auth)");
    expect(items[1].status).toBe("ok");
    expect(items[1].detail).toBe("3 passed, 1 failed");
    expect(items[2].status).toBe("error");
  });
});

describe("parseLiveActivity — generic / fallback", () => {
  it("plain narration (agy) is a single streaming text item", () => {
    const items = parseLiveActivity(
      "antigravity",
      "I will examine the workspace.\nI will check files.\n",
      "",
    );
    expect(items).toHaveLength(1);
    expect(items[0].kind).toBe("text");
  });

  it("surfaces stderr when stdout is silent (auth errors, crashes)", () => {
    const items = parseLiveActivity(
      "antigravity",
      "",
      "Error: not logged in\nRun `agy login` first\n",
    );
    expect(items).toHaveLength(1);
    expect(items[0].kind).toBe("meta");
    expect(items[0].text).toContain("not logged in");
  });

  it("returns nothing for a run that has not spoken yet", () => {
    expect(parseLiveActivity("claude", "", "")).toEqual([]);
  });
});
