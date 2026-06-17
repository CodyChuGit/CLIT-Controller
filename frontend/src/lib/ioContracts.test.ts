import { describe, expect, it } from "vitest";

import { buildSubmission, validateOutputEvent, validateSubmission } from "./ioContracts";

describe("ioContracts (I/O rebuild — typed, runtime-validated, fail-safe)", () => {
  it("builds a well-formed submission with explicit destination + intent", () => {
    const sub = buildSubmission({
      id: "s1",
      workspaceId: "/ws",
      destination: { kind: "task", taskId: "t1", intent: "continue" },
      text: "keep going",
      references: [{ kind: "file", path: "a.py" }],
      submitMode: "continue",
      createdAt: "2026-06-18T00:00:00Z",
    });
    expect(sub.schemaVersion).toBe("1");
    expect(sub.destination).toEqual({ kind: "task", taskId: "t1", intent: "continue" });
    expect(sub.behavior.submitMode).toBe("continue");
    expect(validateSubmission(sub)).not.toBeNull();
  });

  it("rejects empty text, unsupported version, and non-objects", () => {
    expect(
      validateSubmission({
        schemaVersion: "1",
        id: "s",
        workspaceId: "/ws",
        destination: { kind: "controller" },
        content: { text: "" },
      }),
    ).toBeNull();
    expect(
      validateSubmission({
        schemaVersion: "2",
        id: "s",
        workspaceId: "/ws",
        destination: { kind: "controller" },
        content: { text: "x" },
      }),
    ).toBeNull();
    expect(validateSubmission(null)).toBeNull();
    expect(validateSubmission("nope")).toBeNull();
  });

  it("validates a typed output event payload", () => {
    const env = validateOutputEvent({
      schemaVersion: "1",
      id: "e1",
      workspaceId: "/ws",
      createdAt: "t",
      redacted: false,
      truncated: false,
      payload: { type: "command.started", command: "npm test" },
    });
    expect(env).not.toBeNull();
    expect(env!.payload.type).toBe("command.started");
  });

  it("rejects unknown payload type and unsupported version (fail-safe)", () => {
    const base = {
      schemaVersion: "1",
      id: "e",
      workspaceId: "/ws",
      createdAt: "t",
      redacted: false,
      truncated: false,
    };
    expect(validateOutputEvent({ ...base, payload: { type: "frobnicate" } })).toBeNull();
    expect(
      validateOutputEvent({
        ...base,
        schemaVersion: "9",
        payload: { type: "failure", title: "x" },
      }),
    ).toBeNull();
  });
});
