import { render } from "@testing-library/react";
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
