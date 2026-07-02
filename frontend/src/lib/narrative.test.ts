import { describe, expect, it } from "vitest";

import { stripResultSentinel } from "./narrative";

/* The deterministic CLITC_RESULT_V1 block (Plane 3) must never render as prose in
   any chat box — neither the final bubble nor the live stream. */
describe("stripResultSentinel", () => {
  const BLOCK =
    '<<<CLITC_RESULT_V1\n{"schemaVersion":"1","kind":"controller_result",' +
    '"message":{"summary":"ok","details":[]},"action":{"type":"answer"}}\nCLITC_RESULT_V1>>>';

  it("keeps the prose and drops the result block", () => {
    const out = stripResultSentinel(`Here is my plan.\n\n${BLOCK}`);
    expect(out).toBe("Here is my plan.");
    expect(out).not.toContain("CLITC_RESULT_V1");
  });

  it("returns empty when the reply is only a block", () => {
    expect(stripResultSentinel(BLOCK)).toBe("");
  });

  it("strips a partial leading sentinel mid-stream", () => {
    // The live stream may arrive with the sentinel half-emitted.
    expect(stripResultSentinel("Working on it.\n<<<CLITC_RESULT_V1\n{")).toBe("Working on it.");
  });

  it("passes ordinary prose through unchanged", () => {
    expect(stripResultSentinel("just a normal reply")).toBe("just a normal reply");
  });
});
