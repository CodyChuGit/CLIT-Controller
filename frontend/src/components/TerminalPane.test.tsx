/** TerminalPane must take keyboard focus — a rendered prompt that silently
 *  drops keystrokes (no focus on mount, padding clicks missing xterm's own
 *  click-to-focus) is indistinguishable from "the terminal is broken". */
import { render, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// jsdom provides neither; the component needs both to mount. The WebSocket
// stub also keeps tests from dialing the real backend.
vi.stubGlobal(
  "ResizeObserver",
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
);
vi.stubGlobal(
  "WebSocket",
  class {
    static OPEN = 1;
    readyState = 0;
    binaryType = "blob";
    onopen: unknown = null;
    onmessage: unknown = null;
    onclose: unknown = null;
    onerror: unknown = null;
    send() {}
    close() {}
  },
);

const focus = vi.fn();

vi.mock("@xterm/xterm", () => ({
  Terminal: vi.fn().mockImplementation(() => ({
    loadAddon: vi.fn(),
    open: vi.fn(),
    focus,
    dispose: vi.fn(),
    onData: vi.fn(() => ({ dispose: vi.fn() })),
    onResize: vi.fn(() => ({ dispose: vi.fn() })),
    rows: 24,
    cols: 80,
  })),
}));
vi.mock("@xterm/addon-fit", () => ({
  FitAddon: vi.fn().mockImplementation(() => ({ fit: vi.fn() })),
}));
vi.mock("../api", () => ({
  api: { terminalDiagnostics: vi.fn(() => new Promise(() => {})), terminalKill: vi.fn() },
}));

import TerminalPane from "./TerminalPane";

describe("TerminalPane focus", () => {
  it("focuses the terminal on mount so typing works without a precise click", () => {
    render(<TerminalPane provider="antigravity" />);
    expect(focus).toHaveBeenCalled();
  });

  it("re-focuses when the terminal area is clicked (padding included)", () => {
    const { container } = render(<TerminalPane provider="antigravity" />);
    focus.mockClear();
    const mount = container.querySelector("[data-terminal-mount]");
    expect(mount).not.toBeNull();
    fireEvent.click(mount!);
    expect(focus).toHaveBeenCalled();
  });
});
