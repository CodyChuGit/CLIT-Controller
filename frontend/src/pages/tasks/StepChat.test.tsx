import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Exchange, TaskDetail } from "../../types";
import StepChat from "./StepChat";

/* UI tests for the task step chat box. The brief (the prompt/context sent to the
   agent) must be HIDDEN by default — the agent's reply is the focus — and an empty
   reply must read as "No output", never as raw log scaffolding. */

function detailFor(step: string): TaskDetail {
  return {
    task: {
      id: "t1",
      title: "T",
      goal: "g",
      createdAt: "",
      status: "in_progress",
      steps: { [step]: { status: "succeeded", provider: "codex" } },
      fullSequence: { status: "running", currentStep: step },
      events: [],
    },
    taskDir: "",
    files: [],
    runs: [],
    stepPreviews: {
      [step]: {
        step,
        label: "Spec",
        provider: "codex",
        providerInstalled: true,
        commandPreview: "",
        promptChars: 0,
        reads: [],
        writes: [],
      },
    },
  } as unknown as TaskDetail;
}

const STEP = "codex_spec";
const noop = () => {};

function exchange(output: string): Exchange {
  return { stamp: "20260101-120000", prompt: "Write the spec. UNIQUEBRIEFMARKER", output };
}

describe("task step chat box", () => {
  it("shows the agent's reply and hides the brief/context by default", () => {
    const { container } = render(
      <StepChat
        detail={detailFor(STEP)}
        step={STEP}
        exchanges={[exchange("Spec written to 01_CODEX_SPEC.md.")]}
        onRun={noop}
        onOpenFile={noop}
      />,
    );
    // Reply is visible …
    expect(container.textContent).toContain("Spec written to 01_CODEX_SPEC.md.");
    // … the brief is a collapsed toggle, its context not rendered until opened.
    expect(container.textContent).toContain("brief ·");
    expect(container.textContent).not.toContain("UNIQUEBRIEFMARKER");
  });

  it("reveals the brief when its disclosure is opened", () => {
    const { container, getByText } = render(
      <StepChat
        detail={detailFor(STEP)}
        step={STEP}
        exchanges={[exchange("ok")]}
        onRun={noop}
        onOpenFile={noop}
      />,
    );
    fireEvent.click(getByText(/brief ·/));
    expect(container.textContent).toContain("UNIQUEBRIEFMARKER");
  });

  it("collapses an empty/cancelled exchange to a muted 'no reply' line, not a bubble", () => {
    const { container } = render(
      <StepChat
        detail={detailFor(STEP)}
        step={STEP}
        exchanges={[exchange("")]}
        onRun={noop}
        onOpenFile={noop}
      />,
    );
    // One subtle line, no "No output." bubble and no log scaffolding.
    expect(container.textContent).toContain("no reply");
    expect(container.textContent).not.toContain("No output.");
    expect(container.textContent).not.toContain("--- STDOUT ---");
    expect(container.textContent).not.toContain("Command Line Interface Terminal Controller run");
  });
});
