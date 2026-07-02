import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Message } from "./Message";

/* UI tests for the shared chat-box renderer (the controller dock and the provider
   direct chats both render through Message). The deterministic CLITC_RESULT_V1
   block must never leak into a bubble — including historical messages stored raw
   before the backend started cleaning them. */

const BLOCK =
  '<<<CLITC_RESULT_V1\n{"schemaVersion":"1","kind":"controller_result",' +
  '"message":{"summary":"done","details":[]},"action":{"type":"answer"}}\nCLITC_RESULT_V1>>>';

describe("controller chat box", () => {
  it("renders the controller's prose and strips the result block", () => {
    const { container } = render(
      <Message
        msg={{
          role: "assistant",
          provider: "antigravity",
          content: `I'll set up a security audit.\n\n${BLOCK}`,
          time: "t",
        }}
      />,
    );
    expect(container.textContent).toContain("I'll set up a security audit.");
    expect(container.textContent).not.toContain("CLITC_RESULT_V1");
    expect(container.textContent).not.toContain("schemaVersion");
  });

  it("never shows raw JSON even for a block-only message", () => {
    const { container } = render(
      <Message msg={{ role: "assistant", provider: "antigravity", content: BLOCK, time: "t" }} />,
    );
    expect(container.textContent).not.toContain("CLITC_RESULT_V1");
    expect(container.textContent).not.toContain("controller_result");
  });
});

describe("provider direct chat box", () => {
  it("attributes the reply to the provider and shows its content", () => {
    const { container } = render(
      <Message
        msg={{ role: "assistant", provider: "codex", content: "done — wrote two files", time: "t" }}
        direct
      />,
    );
    expect(container.textContent).toContain("codex");
    expect(container.textContent).toContain("done — wrote two files");
  });

  it("keeps the user's own message verbatim", () => {
    const { container } = render(
      <Message msg={{ role: "user", content: "run the tests", time: "t" }} />,
    );
    expect(container.textContent).toContain("run the tests");
  });
});
