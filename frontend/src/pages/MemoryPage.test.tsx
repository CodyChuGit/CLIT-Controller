import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// The galaxy pulls in three.js/WebGL — stub it; we only assert routing here.
vi.mock("./MemoryGalaxy", () => ({
  default: () => <div data-testid="galaxy">galaxy</div>,
}));

vi.mock("../api", async (orig) => {
  const actual = (await orig()) as typeof import("../api");
  return {
    ...actual,
    api: { memoryStatus: vi.fn(), memoryIndex: vi.fn() },
  };
});

import { api } from "../api";
import MemoryPage from "./MemoryPage";

const mockApi = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

describe("MemoryPage", () => {
  it("shows the not-installed state", async () => {
    mockApi.memoryStatus.mockResolvedValue({ available: false, project: null });
    render(<MemoryPage />);
    expect(await screen.findByText(/not installed/i)).toBeInTheDocument();
  });

  it("prompts to index an un-indexed workspace", async () => {
    mockApi.memoryStatus.mockResolvedValue({ available: true, project: null });
    render(<MemoryPage />);
    expect(await screen.findByText(/build its knowledge graph/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /index workspace/i })).toBeInTheDocument();
  });

  it("renders the native galaxy for an indexed workspace", async () => {
    mockApi.memoryStatus.mockResolvedValue({ available: true, project: "demo" });
    render(<MemoryPage />);
    expect(await screen.findByTestId("galaxy")).toBeInTheDocument();
  });
});
