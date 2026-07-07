import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../api", async (orig) => {
  const actual = (await orig()) as typeof import("../api");
  return {
    ...actual,
    api: {
      opensrcStatus: vi.fn(),
      opensrcList: vi.fn().mockResolvedValue([]),
      opensrcFetch: vi.fn(),
      opensrcTree: vi.fn(),
      opensrcFile: vi.fn(),
      opensrcSearch: vi.fn(),
    },
  };
});

import { api } from "../api";
import SourcesPage from "./SourcesPage";

const mockApi = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

describe("SourcesPage", () => {
  it("shows the not-installed state", async () => {
    mockApi.opensrcStatus.mockResolvedValue({ available: false });
    render(<SourcesPage />);
    expect(await screen.findByText(/not installed/i)).toBeInTheDocument();
  });

  it("renders fetch UI and cached packages when available", async () => {
    mockApi.opensrcStatus.mockResolvedValue({ available: true });
    mockApi.opensrcList.mockResolvedValue([{ name: "zod", path: "/x/zod" }]);
    render(<SourcesPage />);
    expect(await screen.findByText("Fetch")).toBeInTheDocument();
    expect(await screen.findByText("zod")).toBeInTheDocument();
  });
});
