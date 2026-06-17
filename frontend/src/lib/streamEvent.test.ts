import { describe, expect, it } from "vitest";

import { coerceStreamEvent } from "./streamEvent";

describe("coerceStreamEvent (Pillar 5 / P2-14 — validate network input)", () => {
  it("accepts a well-formed frame and normalizes nullable fields", () => {
    const ev = coerceStreamEvent({ id: 7, type: "run.output", textDelta: "hi" });
    expect(ev).not.toBeNull();
    expect(ev!.id).toBe(7);
    expect(ev!.type).toBe("run.output");
    expect(ev!.textDelta).toBe("hi");
    expect(ev!.provider).toBeNull();
    expect(ev!.data).toEqual({});
    expect(ev!.redacted).toBe(false);
  });

  it("rejects frames missing the load-bearing id/type", () => {
    expect(coerceStreamEvent({ type: "run.output" })).toBeNull();
    expect(coerceStreamEvent({ id: 1 })).toBeNull();
    expect(coerceStreamEvent({ id: "1", type: "x" })).toBeNull();
  });

  it("rejects non-objects", () => {
    expect(coerceStreamEvent(null)).toBeNull();
    expect(coerceStreamEvent("a string")).toBeNull();
    expect(coerceStreamEvent(42)).toBeNull();
  });

  it("coerces a malformed data field to an empty object", () => {
    const ev = coerceStreamEvent({ id: 1, type: "x", data: "not-an-object" });
    expect(ev!.data).toEqual({});
  });
});
