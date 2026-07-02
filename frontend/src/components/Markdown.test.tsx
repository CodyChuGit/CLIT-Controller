import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "./Markdown";

/* Agent/CLI output is untrusted and flows straight into <Markdown>. The renderer
   builds React elements from parsed text (never dangerouslySetInnerHTML), so HTML
   in the model must surface as inert text, never as live DOM. This pins finding
   P3-37 (no agent output is rendered as raw HTML). */
describe("Markdown XSS-safety", () => {
  it("renders embedded HTML/script as text, not live DOM nodes", () => {
    const hostile = '<img src=x onerror="alert(1)"> and <script>alert(2)</script>';
    const { container } = render(<Markdown content={hostile} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    // The angle-bracket markup is preserved verbatim as text content.
    expect(container.textContent).toContain("<img");
    expect(container.textContent).toContain("<script>");
  });

  it("renders ordinary prose content", () => {
    const { container } = render(<Markdown content={"Hello **world**"} />);
    expect(container.textContent).toContain("Hello");
    expect(container.textContent).toContain("world");
  });
});

/* Agent replies link to task artifacts with absolute paths. The renderer must show
   just the file name (the app's chip convention), not dump the whole path. */
describe("Markdown links", () => {
  it("renders a file-path link as the bare file name, not the full path", () => {
    const md =
      "Wrote [02_CODEX_IMPLEMENTATION_PLAN.md]" +
      "(/Users/cody/TestApp/.agentflow/tasks/x/02_CODEX_IMPLEMENTATION_PLAN.md).";
    const { container } = render(<Markdown content={md} />);
    expect(container.textContent).toContain("02_CODEX_IMPLEMENTATION_PLAN");
    // No path, no ".md" extension, no raw markdown syntax.
    expect(container.textContent).not.toContain("/Users/cody");
    expect(container.textContent).not.toContain(".agentflow");
    expect(container.textContent).not.toContain("02_CODEX_IMPLEMENTATION_PLAN.md");
    expect(container.textContent).not.toContain("](");
  });

  it("renders an http link as a real anchor", () => {
    const { container } = render(
      <Markdown content={"See [the guide](https://example.com/guide)."} />,
    );
    const a = container.querySelector("a");
    expect(a?.getAttribute("href")).toBe("https://example.com/guide");
    expect(a?.getAttribute("target")).toBe("_blank");
    expect(a?.textContent).toContain("the guide");
  });

  it("opens the artifact on click when a handler is wired", () => {
    let opened = "";
    const { getByRole } = render(
      <Markdown
        content={"[01_CODEX_SPEC.md](/x/01_CODEX_SPEC.md)"}
        onOpenFile={(n) => (opened = n)}
      />,
    );
    fireEvent.click(getByRole("button"));
    expect(opened).toBe("01_CODEX_SPEC.md"); // basename with extension reaches the opener
  });
});
