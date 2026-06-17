import { describe, expect, it } from "vitest";

import { describeCommand, formatDuration, shortPath } from "./taskFormat";

describe("formatDuration", () => {
  it("renders sub-second durations as milliseconds", () => {
    expect(formatDuration(340)).toBe("340ms");
  });
  it("renders single-digit seconds with one decimal", () => {
    expect(formatDuration(1200)).toBe("1.2s");
  });
  it("renders minutes and seconds", () => {
    expect(formatDuration(124000)).toBe("2m 4s");
  });
  it("returns null for null/undefined/negative", () => {
    expect(formatDuration(null)).toBeNull();
    expect(formatDuration(undefined)).toBeNull();
    expect(formatDuration(-5)).toBeNull();
  });
});

describe("shortPath", () => {
  it("keeps short paths intact", () => {
    expect(shortPath("/a/b")).toBe("/a/b");
  });
  it("collapses long paths to the last two segments", () => {
    expect(shortPath("/Users/cody/AgentComposer/backend")).toBe("…/AgentComposer/backend");
  });
  it("returns null for empty input", () => {
    expect(shortPath(null)).toBeNull();
    expect(shortPath(undefined)).toBeNull();
  });
});

describe("describeCommand", () => {
  it("falls back to the basename for unknown commands", () => {
    expect(describeCommand("/usr/local/bin/foobar --x")).toBe("Run foobar");
  });
  it("handles empty input", () => {
    expect(describeCommand("")).toBe("Run command");
  });
});
