import { describe, expect, it } from "vitest";

import { isNearBottom } from "./useAutoScroll";

describe("isNearBottom (Pillar 4 — consistent auto-scroll)", () => {
  it("is true at the exact bottom", () => {
    // scrollTop + clientHeight === scrollHeight
    expect(isNearBottom(800, 1000, 200)).toBe(true);
  });

  it("is true within the threshold of the bottom", () => {
    expect(isNearBottom(770, 1000, 200)).toBe(true); // 30px from bottom
  });

  it("is false when scrolled up past the threshold", () => {
    expect(isNearBottom(200, 1000, 200)).toBe(false); // 600px from bottom
  });

  it("respects a custom threshold", () => {
    expect(isNearBottom(700, 1000, 200, 150)).toBe(true); // 100px, threshold 150
    expect(isNearBottom(700, 1000, 200, 50)).toBe(false); // 100px, threshold 50
  });
});
