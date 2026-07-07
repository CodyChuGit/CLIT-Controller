import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("react-force-graph-3d", () => ({ default: () => <div data-testid="fg3d" /> }));
vi.mock("../api", async (orig) => {
  const actual = (await orig()) as typeof import("../api");
  return {
    ...actual,
    api: {
      memoryStatus: vi.fn(),
      memorySchema: vi.fn(),
      memoryGraph: vi.fn(),
      memoryArchitecture: vi.fn().mockResolvedValue({}),
      memoryIndex: vi.fn(),
      memorySnippet: vi.fn(),
      memoryTrace: vi.fn(),
    },
  };
});

import { api } from "../api";
import MemoryPage from "./MemoryPage";

const mockApi = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

beforeAll(() => {
  // jsdom has no ResizeObserver
  (globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

describe("MemoryPage", () => {
  it("shows the not-installed state", async () => {
    mockApi.memoryStatus.mockResolvedValue({ available: false });
    render(<MemoryPage />);
    expect(await screen.findByText(/not installed/i)).toBeInTheDocument();
  });

  it("renders the control panel and node count when indexed", async () => {
    mockApi.memoryStatus.mockResolvedValue({ available: true, project: "demo" });
    mockApi.memorySchema.mockResolvedValue({ node_labels: [{ label: "Function", count: 3 }] });
    mockApi.memoryGraph.mockResolvedValue({
      nodes: [{ id: "demo.foo", label: "Function", name: "foo", file: "foo.py", degree: 1 }],
      edges: [],
    });
    mockApi.memoryArchitecture.mockResolvedValue({
      hotspots: [{ name: "hot", qualified_name: "demo.hot", fan_in: 9 }],
    });
    render(<MemoryPage />);
    expect(await screen.findByText("Index now")).toBeInTheDocument();
    expect(await screen.findByText(/Project: demo/)).toBeInTheDocument();
    expect(await screen.findByText(/1 nodes/)).toBeInTheDocument();
    expect(await screen.findByText("hot")).toBeInTheDocument();
  });
});
