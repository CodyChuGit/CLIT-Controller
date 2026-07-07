import { useCallback, useEffect, useMemo, useRef, useState } from "react";
// react-force-graph-3d pulls in three.js; this page is lazy-loaded from App so it
// stays out of the initial bundle.
import ForceGraph3D from "react-force-graph-3d";

import { api, ApiError } from "../api";
import type { GraphData, GraphNode, MemoryStatus } from "../types";

// Node color by label — an accessible categorical set that reads in light + dark.
// Color is never the *only* signal: the legend and node tooltips carry the label text.
const NODE_COLORS: Record<string, string> = {
  Function: "#3b82f6",
  Method: "#0ea5e9",
  Class: "#8b5cf6",
  Interface: "#a855f7",
  Module: "#10b981",
  File: "#22c55e",
  Folder: "#16a34a",
  Package: "#059669",
  Route: "#f59e0b",
  Enum: "#ec4899",
  Type: "#14b8a6",
  Resource: "#f97316",
  Project: "#ef4444",
};
const colorFor = (label: string) => NODE_COLORS[label] ?? "#9ca3af";

// The app themes via Tailwind's `media` strategy (prefers-color-scheme), not a
// `.dark` class — so match the OS setting to keep the WebGL canvas in sync.
function useIsDark(): boolean {
  const QUERY = "(prefers-color-scheme: dark)";
  const [dark, setDark] = useState(() => window.matchMedia?.(QUERY).matches ?? true);
  useEffect(() => {
    const mq = window.matchMedia(QUERY);
    const onChange = (e: MediaQueryListEvent) => setDark(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return dark;
}

/** Measure a container so the WebGL canvas fills it (avoids window-sized default). */
function useSize(ref: React.RefObject<HTMLElement>) {
  const [size, setSize] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) =>
      setSize({ w: e.contentRect.width, h: e.contentRect.height }),
    );
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return size;
}

interface NodeDetail {
  node: GraphNode;
  source?: string;
  callers: string[];
  callees: string[];
  loading: boolean;
}

export default function MemoryPage() {
  const isDark = useIsDark();
  const canvasRef = useRef<HTMLDivElement>(null);
  const { w, h } = useSize(canvasRef);

  const [status, setStatus] = useState<MemoryStatus | null>(null);
  const [labels, setLabels] = useState<{ label: string; count: number }[]>([]);
  const [hotspots, setHotspots] = useState<
    { name: string; qualified_name: string; fan_in: number }[]
  >([]);
  const [data, setData] = useState<GraphData>({ nodes: [], edges: [] });
  const [label, setLabel] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<NodeDetail | null>(null);

  const graphData = useMemo(
    () => ({
      nodes: data.nodes.map((n) => ({ ...n })),
      links: data.edges.map((e) => ({ source: e.source, target: e.target, type: e.type })),
    }),
    [data],
  );

  const loadStatus = useCallback(async () => {
    try {
      const s = await api.memoryStatus();
      setStatus(s);
      if (s.available && s.project) {
        const schema = (await api.memorySchema()) as {
          node_labels?: { label: string; count: number }[];
        };
        setLabels(schema.node_labels ?? []);
        try {
          const arch = (await api.memoryArchitecture()) as {
            hotspots?: { name: string; qualified_name: string; fan_in: number }[];
          };
          setHotspots(arch.hotspots ?? []);
        } catch {
          /* architecture summary is optional */
        }
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);

  const loadGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(
        await api.memoryGraph({ label: label || undefined, name: name || undefined, limit: 300 }),
      );
    } catch (e) {
      if (e instanceof ApiError && e.status === 404)
        setError("This workspace isn't indexed yet — click “Index now”.");
      else setError(e instanceof ApiError ? e.message : String(e));
      setData({ nodes: [], edges: [] });
    } finally {
      setLoading(false);
    }
  }, [label, name]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (status?.available && status.project) void loadGraph();
  }, [status?.available, status?.project, loadGraph]);

  const onIndex = async () => {
    setIndexing(true);
    setError(null);
    try {
      await api.memoryIndex();
      await loadStatus();
      await loadGraph();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setIndexing(false);
    }
  };

  const onNodeClick = async (node: GraphNode) => {
    setDetail({ node, callers: [], callees: [], loading: true });
    try {
      const [snip, tr] = await Promise.all([
        api.memorySnippet(node.id) as Promise<{
          source?: string;
          caller_names?: string[];
          callee_names?: string[];
        }>,
        api.memoryTrace(node.name, 2).catch(() => ({ nodes: [], edges: [] })),
      ]);
      void tr;
      setDetail({
        node,
        source: snip.source,
        callers: snip.caller_names ?? [],
        callees: snip.callee_names ?? [],
        loading: false,
      });
    } catch {
      setDetail({ node, callers: [], callees: [], loading: false });
    }
  };

  // --- gated states ---------------------------------------------------------
  if (status && !status.available) {
    return (
      <Centered>
        <h2 className="text-sm font-semibold text-neutral-800 dark:text-neutral-200">
          Codebase Memory not installed
        </h2>
        <p className="mt-1 max-w-sm text-xs text-neutral-500">
          The{" "}
          <code className="rounded bg-neutral-100 px-1 py-0.5 dark:bg-neutral-800">
            codebase-memory-mcp
          </code>{" "}
          tool powers this graph. Install it from the <strong>Agents</strong> tab, then reload.
        </p>
      </Centered>
    );
  }

  return (
    <div className="flex h-full min-h-0">
      {/* Control panel */}
      <div className="flex w-60 shrink-0 flex-col gap-4 overflow-y-auto border-r border-neutral-200 p-3 dark:border-neutral-800">
        <div>
          <div className="section-label">Index</div>
          <button
            className="btn-primary mt-1 w-full justify-center"
            onClick={onIndex}
            disabled={indexing}
          >
            {indexing ? "Indexing…" : "Index now"}
          </button>
          <p className="mt-1.5 text-[11px] text-neutral-500">
            {status?.project ? `Project: ${status.project}` : "Workspace not indexed yet."}
          </p>
        </div>

        <div>
          <div className="section-label">Filter</div>
          <select
            className="input mt-1"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            aria-label="Filter nodes by label"
          >
            <option value="">All labels</option>
            {labels.map((l) => (
              <option key={l.label} value={l.label}>
                {l.label} ({l.count})
              </option>
            ))}
          </select>
          <form
            className="mt-2 flex gap-1.5"
            onSubmit={(e) => {
              e.preventDefault();
              void loadGraph();
            }}
          >
            <input
              className="input"
              placeholder="Search name…"
              value={name}
              onChange={(e) => setName(e.target.value)}
              aria-label="Search nodes by name"
            />
            <button className="btn-secondary" type="submit" aria-label="Apply filters">
              Go
            </button>
          </form>
        </div>

        {labels.length > 0 && (
          <div>
            <div className="section-label">Legend</div>
            <ul className="mt-1 space-y-1">
              {labels.slice(0, 8).map((l) => (
                <li
                  key={l.label}
                  className="flex items-center gap-2 text-[11px] text-neutral-600 dark:text-neutral-300"
                >
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ background: colorFor(l.label) }}
                  />
                  {l.label}
                </li>
              ))}
            </ul>
          </div>
        )}

        {hotspots.length > 0 && (
          <div>
            <div className="section-label">Hotspots</div>
            <ul className="mt-1 space-y-0.5">
              {hotspots.slice(0, 6).map((hs) => (
                <li key={hs.qualified_name}>
                  <button
                    className="focusable w-full truncate rounded px-1 py-0.5 text-left text-[11px] text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
                    title={`${hs.qualified_name} · fan-in ${hs.fan_in}`}
                    onClick={() =>
                      void onNodeClick({
                        id: hs.qualified_name,
                        name: hs.name,
                        label: "Function",
                        file: null,
                        degree: hs.fan_in,
                      })
                    }
                  >
                    {hs.name}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="mt-auto text-[11px] text-neutral-400">
          {data.nodes.length} nodes · {data.edges.length} edges
        </p>
      </div>

      {/* Graph canvas */}
      <div ref={canvasRef} className="relative min-h-0 flex-1">
        {error && (
          <div className="absolute inset-x-0 top-0 z-10 m-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            {error}
          </div>
        )}
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center text-xs text-neutral-400">
            Loading graph…
          </div>
        )}
        {!loading && !error && data.nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-xs text-neutral-400">
            No nodes to show. Index the workspace or widen the filter.
          </div>
        )}
        {w > 0 && (
          <ForceGraph3D
            graphData={graphData}
            width={w}
            height={h}
            backgroundColor={isDark ? "#0a0a0a" : "#ffffff"}
            nodeLabel={(n: GraphNode) => `${n.label}: ${n.name}`}
            nodeColor={(n: GraphNode) => colorFor(n.label)}
            nodeRelSize={4}
            nodeVal={(n: GraphNode) => 1 + Math.min(n.degree || 0, 12)}
            nodeOpacity={0.95}
            linkColor={() => (isDark ? "rgba(148,163,184,0.4)" : "#cbd5e1")}
            linkWidth={0.6}
            linkDirectionalParticles={0}
            onNodeClick={(n: object) => void onNodeClick(n as GraphNode)}
          />
        )}
      </div>

      {/* Node detail drawer */}
      {detail && (
        <div className="flex w-80 shrink-0 flex-col gap-3 overflow-y-auto border-l border-neutral-200 p-3 dark:border-neutral-800">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="text-xs font-semibold text-neutral-800 dark:text-neutral-200">
                {detail.node.name}
              </div>
              <div className="text-[11px] text-neutral-500">
                {detail.node.label}
                {detail.node.file ? ` · ${detail.node.file}` : ""}
              </div>
            </div>
            <button className="icon-btn" onClick={() => setDetail(null)} aria-label="Close details">
              ✕
            </button>
          </div>
          {detail.loading ? (
            <p className="text-[11px] text-neutral-400">Loading…</p>
          ) : (
            <>
              {detail.source && (
                <pre className="mono-block max-h-64 whitespace-pre-wrap">{detail.source}</pre>
              )}
              <RefList title="Callers" items={detail.callers} />
              <RefList title="Callees" items={detail.callees} />
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full flex-col items-center justify-center p-6 text-center">
      {children}
    </div>
  );
}

function RefList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <div className="section-label">{title}</div>
      <ul className="mt-1 space-y-0.5">
        {items.slice(0, 20).map((it) => (
          <li
            key={it}
            className="truncate font-mono text-[11px] text-neutral-600 dark:text-neutral-300"
            title={it}
          >
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}
