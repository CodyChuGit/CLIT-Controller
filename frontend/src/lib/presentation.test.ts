import { describe, expect, it } from "vitest";

import type { StreamEvent } from "../types";
import type { EventPayload } from "./ioContracts";
import { recordFromEvent } from "./presentation";

function ev(payload: EventPayload | null, provider: string | null = null): StreamEvent {
  return {
    id: 1,
    type: "x",
    createdAt: "t",
    time: "t",
    workspacePath: "/ws",
    provider,
    taskId: null,
    runId: null,
    queueItemId: null,
    step: null,
    sequence: null,
    channel: null,
    textDelta: null,
    redacted: true,
    truncated: false,
    detail: "",
    data: {},
    payload,
  };
}

describe("recordFromEvent (derive records from typed payload, not prose)", () => {
  it("maps each payload type to its record kind", () => {
    expect(recordFromEvent(ev({ type: "narrative.delta", text: "hi" }, "codex"))).toEqual({
      kind: "narrative",
      text: "hi",
      provider: "codex",
    });
    expect(recordFromEvent(ev({ type: "command.started", command: "npm test" }))).toMatchObject({
      kind: "command",
      command: "npm test",
      status: "running",
    });
    expect(
      recordFromEvent(ev({ type: "command.completed", status: "failed", exitCode: 1 })),
    ).toMatchObject({
      kind: "command",
      status: "failed",
      exitCode: 1,
    });
    expect(
      recordFromEvent(ev({ type: "approval.requested", approvalId: "a1", action: "git push" })),
    ).toMatchObject({
      kind: "approval",
      action: "git push",
    });
    expect(recordFromEvent(ev({ type: "failure", title: "Boom", summary: "why" }))).toEqual({
      kind: "failure",
      title: "Boom",
      summary: "why",
    });
    expect(recordFromEvent(ev({ type: "summary.ready", kind: "test_summary" }))).toEqual({
      kind: "summary",
      summaryKind: "test_summary",
    });
  });

  it("returns null for an event with no typed payload (transport-only)", () => {
    expect(recordFromEvent(ev(null))).toBeNull();
  });
});
