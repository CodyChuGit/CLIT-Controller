import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InputComposer from "./InputComposer";

const submit = vi.fn();
vi.mock("../../api", () => ({ api: { chatSubmit: (...args: unknown[]) => submit(...args) } }));

beforeEach(() => {
  submit.mockReset();
  localStorage.clear();
});

describe("InputComposer (typed input plane)", () => {
  it("submits a typed InputSubmission with explicit task destination + intent", async () => {
    submit.mockResolvedValue({ status: "sent" });
    render(
      <InputComposer
        workspaceId="ws"
        destination={{ kind: "task", taskId: "task-9", intent: "continue" }}
        submitMode="continue"
      />,
    );
    const ta = screen.getByLabelText("Message") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "keep going" } });
    fireEvent.keyDown(ta, { key: "Enter" });
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
    const sub = submit.mock.calls[0][0];
    expect(sub.schemaVersion).toBe("1");
    expect(sub.destination).toEqual({ kind: "task", taskId: "task-9", intent: "continue" });
    expect(sub.content.text).toBe("keep going");
    expect(sub.behavior.submitMode).toBe("continue");
    await waitFor(() => expect(ta.value).toBe("")); // cleared on success
  });

  it("preserves the draft on a failed submit", async () => {
    submit.mockResolvedValueOnce({ status: "error", message: "boom" });
    render(<InputComposer workspaceId="ws" destination={{ kind: "controller" }} />);
    const ta = screen.getByLabelText("Message") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "draft text" } });
    fireEvent.keyDown(ta, { key: "Enter" });
    await waitFor(() => expect(submit).toHaveBeenCalled());
    expect(ta.value).toBe("draft text"); // not cleared on error
    expect(localStorage.getItem("agentflow.draft.ws.controller")).toContain("draft text");
  });

  it("restores a persisted draft on mount", () => {
    localStorage.setItem("agentflow.draft.ws.controller", JSON.stringify("restored draft"));
    render(<InputComposer workspaceId="ws" destination={{ kind: "controller" }} />);
    expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe("restored draft");
  });
});
