import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RecordView from "./RecordView";

describe("RecordView (selects component by record kind)", () => {
  it("renders a command record with status + exit", () => {
    const { container } = render(
      <RecordView
        record={{ kind: "command", command: "npm test", status: "failed", exitCode: 1 }}
      />,
    );
    expect(container.textContent).toContain("npm test");
    expect(container.textContent).toContain("failed");
    expect(container.textContent).toContain("exit 1");
  });

  it("renders a failure record as an alert", () => {
    render(
      <RecordView record={{ kind: "failure", title: "Build failed", summary: "two errors" }} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Build failed");
    expect(screen.getByRole("alert")).toHaveTextContent("two errors");
  });

  it("renders a summary record", () => {
    const { container } = render(
      <RecordView record={{ kind: "summary", summaryKind: "test_summary" }} />,
    );
    expect(container.textContent).toContain("test summary");
  });

  it("returns null for kinds rendered elsewhere (narrative)", () => {
    const { container } = render(<RecordView record={{ kind: "narrative", text: "hi" }} />);
    expect(container.firstChild).toBeNull();
  });
});
