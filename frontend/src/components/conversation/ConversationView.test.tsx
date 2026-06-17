import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConversationView } from "./ConversationView";
import { Message } from "./Message";

/* Pillar 4 — one shared message renderer across every chat surface. */
describe("conversation primitives", () => {
  it("renders a user message as plain text", () => {
    render(<Message msg={{ role: "user", content: "hello there", time: "t" }} />);
    expect(screen.getByText("hello there")).toBeInTheDocument();
  });

  it("renders an assistant message attributed to its provider", () => {
    const { container } = render(
      <Message
        msg={{ role: "assistant", content: "hi from codex", provider: "codex", time: "t" }}
      />,
    );
    expect(container.textContent).toContain("codex");
    expect(container.textContent).toContain("hi from codex");
  });

  it("renders a system notice (controller strip)", () => {
    const { container } = render(
      <Message msg={{ role: "system", content: "Created task X", time: "t" }} />,
    );
    expect(container.textContent).toContain("Created task X");
  });

  it("ConversationView shows the empty state, then lists messages", () => {
    const { rerender, container } = render(
      <ConversationView messages={[]} empty={<div>nothing yet</div>} />,
    );
    expect(screen.getByText("nothing yet")).toBeInTheDocument();
    rerender(
      <ConversationView
        messages={[
          { role: "user", content: "question", time: "t1" },
          { role: "assistant", content: "answer", provider: "claude", time: "t2" },
        ]}
      />,
    );
    expect(container.textContent).toContain("question");
    expect(container.textContent).toContain("answer");
  });

  it("ConversationView renders trailing live content", () => {
    const { container } = render(
      <ConversationView messages={[]} trailing={<div>streaming…</div>} />,
    );
    expect(container.textContent).toContain("streaming…");
  });
});
