import { describe, expect, it } from "vitest";

import { hasAnsi, stripAnsi } from "./ansi";

const ESC = "\x1b";

describe("stripAnsi (Pillar 3 — readable presentation)", () => {
  it("removes SGR color codes but keeps the text", () => {
    const colored = `${ESC}[31mERROR${ESC}[0m: build failed`;
    expect(stripAnsi(colored)).toBe("ERROR: build failed");
  });

  it("removes cursor-move / erase sequences", () => {
    expect(stripAnsi(`progress${ESC}[2K${ESC}[1Gdone`)).toBe("progressdone");
  });

  it("leaves plain text untouched", () => {
    expect(stripAnsi("plain log line")).toBe("plain log line");
  });

  it("handles null/empty", () => {
    expect(stripAnsi(null)).toBe("");
    expect(stripAnsi(undefined)).toBe("");
  });

  it("hasAnsi detects escapes", () => {
    expect(hasAnsi(`${ESC}[32mok${ESC}[0m`)).toBe(true);
    expect(hasAnsi("no escapes here")).toBe(false);
  });
});
