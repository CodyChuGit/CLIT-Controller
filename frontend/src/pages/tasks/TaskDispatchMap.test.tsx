import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { QueueState, TaskDetail } from "../../types";
import TaskDispatchMap from "./TaskDispatchMap";

/* The dispatch map must explain distribution: each step appears in its
   provider's lane (not a linear chart), queue state overlays stale step state,
   and blocked work is visible in context. */

function detail(): TaskDetail {
  const preview = (step: string, provider: string) => ({
    step,
    label: step,
    provider,
    providerInstalled: true,
    commandPreview: "",
    promptChars: 0,
    reads: [],
    writes: [],
  });
  return {
    task: {
      id: "t1",
      title: "T",
      goal: "g",
      createdAt: "",
      status: "in_progress",
      steps: {
        codex_spec: { status: "succeeded", artifactsWritten: ["01_CODEX_SPEC.md"] },
        claude_implement: { status: "running" },
      },
      fullSequence: { status: "running", currentStep: "claude_implement" },
      events: [],
      consults: 2,
    },
    taskDir: "",
    files: [],
    runs: [],
    stepPreviews: {
      codex_spec: preview("codex_spec", "codex"),
      claude_implement: preview("claude_implement", "claude"),
      gemini_qa: preview("gemini_qa", "antigravity"),
      codex_review: preview("codex_review", "codex"),
      claude_fix: preview("claude_fix", "claude"),
    },
  } as unknown as TaskDetail;
}

const queue: QueueState = {
  items: [
    {
      id: "q1",
      taskId: "t1",
      step: "gemini_qa",
      label: "QA",
      provider: "antigravity",
      status: "awaiting_approval",
      source: "orchestrator",
      enqueuedAt: "",
      note: null,
      runId: null,
    },
  ],
  activeCount: 1,
} as unknown as QueueState;

describe("task dispatch map", () => {
  it("groups work into provider lanes with lane roles", () => {
    const { container } = render(
      <TaskDispatchMap detail={detail()} queue={queue} approvals={[]} onSelectStep={() => {}} />,
    );
    const text = container.textContent ?? "";
    for (const lane of ["Controller", "Codex", "Claude", "Antigravity", "Local tools"]) {
      expect(text).toContain(lane);
    }
    // Routing rationale (lane roles) is visible near the work.
    expect(text).toContain("specs · plans · reviews");
    expect(text).toContain("implementation · fixes");
  });

  it("shows queue overlay status (blocked/approval) in the owning lane", () => {
    const { container } = render(
      <TaskDispatchMap detail={detail()} queue={queue} approvals={[]} onSelectStep={() => {}} />,
    );
    // gemini_qa is awaiting approval via the queue overlay, not its idle step
    // state — shown with the terse pill copy.
    expect(container.textContent).toContain("approval");
  });

  it("surfaces pending approvals in the controller lane", () => {
    const approvals = [
      {
        id: "a1",
        action: "git push",
        kind: "command",
        source: "orchestrator",
        provider: "antigravity",
        taskId: "t1",
        reason: "remote write",
        status: "pending",
        createdAt: "",
        resolvedAt: null,
        resolver: null,
      },
    ];
    const { container } = render(
      <TaskDispatchMap
        detail={detail()}
        queue={queue}
        approvals={approvals as never}
        onSelectStep={() => {}}
      />,
    );
    expect(container.textContent).toContain("1 approval waiting");
  });
});
