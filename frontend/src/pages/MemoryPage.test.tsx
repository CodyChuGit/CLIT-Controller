import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../api", async (orig) => {
  const actual = (await orig()) as typeof import("../api");
  return {
    ...actual,
    api: {
      memoryUi: vi.fn(),
      memoryIndex: vi.fn(),
      memoryStatus: vi.fn().mockResolvedValue({ available: true, project: null }),
    },
  };
});

import { api } from "../api";
import MemoryPage from "./MemoryPage";

const mockApi = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

describe("MemoryPage", () => {
  it("shows the not-installed state", async () => {
    mockApi.memoryUi.mockResolvedValue({ available: false, running: false, url: null });
    render(<MemoryPage />);
    expect(await screen.findByText(/not installed/i)).toBeInTheDocument();
  });

  it("embeds the viewer iframe when the sidecar is running", async () => {
    mockApi.memoryUi.mockResolvedValue({
      available: true,
      running: true,
      url: "http://localhost:9749",
    });
    render(<MemoryPage />);
    const iframe = await screen.findByTitle("Codebase Memory graph");
    expect(iframe).toHaveAttribute("src", "http://localhost:9749?tab=graph");
  });
});
