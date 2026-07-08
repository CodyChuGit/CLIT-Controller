import { useCallback, useEffect, useRef, useState, type JSX } from "react";
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { api } from "../api";
import type { TerminalDiagnostics } from "../types";
import { AntigravityMark, ClaudeMark, OpenAIMark } from "./icons";

/* One real PTY terminal pane — a live interactive shell (with the CLI
   auto-launched from its RESOLVED executable path) streamed over a WebSocket.
   Binary frames are raw PTY bytes for xterm.js; JSON text frames are lifecycle
   metadata ({"type":"meta","state":...}) so the header can say exactly where a
   launch is (resolving → launching → ready) or why it died (missing/closed)
   instead of a bare "disconnected". Shared by the Terminals page and the Agent
   Dock terminal drawer. */

const META: Record<string, { name: string; icon: JSX.Element }> = {
  codex: { name: "Codex", icon: <OpenAIMark className="h-3.5 w-3.5" /> },
  claude: { name: "Claude", icon: <ClaudeMark className="h-3.5 w-3.5" /> },
  antigravity: { name: "Antigravity", icon: <AntigravityMark className="h-3.5 w-3.5" /> },
};

// Matches the app's dark surface; xterm needs explicit colors.
const THEME = {
  background: "#0a0a0a",
  foreground: "#e5e5e5",
  cursor: "#e5e5e5",
  selectionBackground: "#3b82f680",
};

type Lifecycle = "resolving" | "missing" | "launching" | "ready" | "closed" | "disconnected";

const LIFECYCLE: Record<Lifecycle, { label: string; dot: string }> = {
  resolving: { label: "resolving executable…", dot: "bg-neutral-500" },
  missing: { label: "not installed", dot: "bg-amber-500" },
  launching: { label: "launching…", dot: "bg-blue-500 animate-pulse" },
  ready: { label: "ready", dot: "bg-emerald-500" },
  closed: { label: "session ended", dot: "bg-rose-500" },
  disconnected: { label: "backend disconnected", dot: "bg-neutral-600" },
};

function wsUrl(provider: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/api/terminals/${provider}/ws`;
}

export default function TerminalPane({
  provider,
  compact = false,
}: {
  provider: string;
  /** Dock-drawer density: tighter header, no rounded frame. */
  compact?: boolean;
}) {
  const meta = META[provider] ?? { name: provider, icon: null };
  const mountRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const termRef = useRef<Terminal | null>(null);
  const reconnectTimer = useRef<number | null>(null);
  const [diag, setDiag] = useState<TerminalDiagnostics | null>(null);
  const [lifecycle, setLifecycle] = useState<Lifecycle>("resolving");
  const [exitCode, setExitCode] = useState<number | null>(null);
  const [epoch, setEpoch] = useState(0); // bump to reconnect / restart the session

  // Executable resolution + failure explanation, refreshed per (re)connect.
  useEffect(() => {
    let stale = false;
    void api
      .terminalDiagnostics(provider)
      .then((d) => {
        if (stale) return;
        setDiag(d);
        // Meta frames own the live state; diagnostics only settles "resolving".
        if (!d.installed) setLifecycle((l) => (l === "resolving" ? "missing" : l));
      })
      .catch(() => {
        /* backend banner covers outages */
      });
    return () => {
      stale = true;
    };
  }, [provider, epoch]);

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;

    const term = new Terminal({
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
      fontSize: 12,
      theme: THEME,
      cursorBlink: true,
      scrollback: 5000,
      convertEol: false,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(el);
    termRef.current = term;
    // Focus immediately: without this the pane renders a live prompt that
    // silently drops every keystroke until the user happens to click exactly
    // on xterm's own screen element ("the terminal is broken").
    term.focus();

    const doFit = () => {
      try {
        fit.fit();
      } catch {
        /* element not measurable yet */
      }
    };
    const rafId = requestAnimationFrame(doFit);

    const ws = new WebSocket(wsUrl(provider));
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      doFit();
      ws.send(JSON.stringify({ type: "resize", rows: term.rows, cols: term.cols }));
    };
    ws.onmessage = (ev) => {
      if (ev.data instanceof ArrayBuffer) {
        term.write(new Uint8Array(ev.data));
        return;
      }
      const text = ev.data as string;
      // JSON meta frames update pane lifecycle; anything else still goes to
      // xterm for compatibility (e.g. the "No workspace" notice).
      try {
        const frame = JSON.parse(text);
        if (frame && frame.type === "meta") {
          setLifecycle(frame.state as Lifecycle);
          if (frame.exitCode !== undefined) setExitCode(frame.exitCode);
          return;
        }
      } catch {
        /* not JSON — raw text */
      }
      term.write(text);
    };
    // Unexpected drops (e.g. the backend restarted) leave a dead pane otherwise:
    // xterm still takes keystrokes but they go nowhere. Auto-reconnect so the
    // session self-heals. Intentional teardown nulls onclose first (see cleanup),
    // so this only fires on real drops.
    ws.onclose = () => {
      setLifecycle((l) => (l === "closed" || l === "missing" ? l : "disconnected"));
      reconnectTimer.current = window.setTimeout(() => setEpoch((e) => e + 1), 1500);
    };
    ws.onerror = () => setLifecycle((l) => (l === "closed" ? l : "disconnected"));

    const dataSub = term.onData((d) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "input", data: d }));
    });
    const resizeSub = term.onResize(({ rows, cols }) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "resize", rows, cols }));
    });

    const ro = new ResizeObserver(() => doFit());
    ro.observe(el);

    return () => {
      cancelAnimationFrame(rafId); // don't fit a disposed terminal after teardown
      if (reconnectTimer.current !== null) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
      ro.disconnect();
      dataSub.dispose();
      resizeSub.dispose();
      ws.onclose = null; // avoid setState + reconnect after unmount/teardown
      ws.close();
      term.dispose();
      wsRef.current = null;
      termRef.current = null;
    };
  }, [provider, epoch]);

  const kill = useCallback(async () => {
    // Kill server-side first (synchronous) so the reconnect can't race the
    // socket teardown and re-attach to the old session.
    try {
      await api.terminalKill(provider);
    } catch {
      /* fall through — reconnect anyway */
    }
    setLifecycle("resolving");
    setExitCode(null);
    setEpoch((e) => e + 1); // tear down and start a fresh session
  }, [provider]);

  const life = LIFECYCLE[lifecycle] ?? LIFECYCLE.resolving;
  const trouble = lifecycle === "missing" || lifecycle === "closed" || lifecycle === "disconnected";

  return (
    <section
      className={`flex min-h-0 flex-1 flex-col overflow-hidden border-neutral-200 dark:border-neutral-800 ${
        compact ? "border-t" : "rounded-lg border"
      }`}
    >
      <header className="flex shrink-0 items-center gap-2 border-b border-neutral-800 bg-neutral-900 px-3 py-1.5">
        <span className="flex items-center gap-1.5 text-neutral-300">
          {meta.icon}
          <span className="text-xs font-semibold">{meta.name}</span>
        </span>
        {diag && !diag.installed && (
          <span className="rounded border border-amber-900 bg-amber-950/40 px-1.5 py-0.5 text-[10px] text-amber-300">
            not installed
          </span>
        )}
        <span className="flex-1" />
        <span className="inline-flex items-center gap-1.5 text-[10px] text-neutral-400">
          <span className={`h-1.5 w-1.5 rounded-full ${life.dot}`} aria-hidden="true" />
          {life.label}
          {lifecycle === "closed" && exitCode !== null && (
            <span className="font-mono">exit {exitCode}</span>
          )}
        </span>
        <button
          onClick={() => void kill()}
          className="focusable cursor-pointer rounded px-1.5 py-0.5 text-[10px] font-medium text-neutral-400 transition-colors hover:bg-neutral-800 hover:text-rose-400"
          title="Kill and restart this session"
        >
          Restart
        </button>
      </header>
      {/* diagnostic strip: the resolved binary, or exactly what failed and what to do */}
      {diag && (trouble || diag.executablePath) && (
        <div className="flex shrink-0 items-center gap-2 border-b border-neutral-800 bg-neutral-950 px-3 py-1 text-[10px]">
          {diag.executablePath ? (
            <span className="truncate font-mono text-neutral-500" title={diag.executablePath}>
              {diag.executablePath}
            </span>
          ) : (
            <span className="text-amber-400">no executable found for {provider}</span>
          )}
          {diag.lastLaunchError && <span className="text-rose-400">{diag.lastLaunchError}</span>}
          {trouble && diag.suggestedAction && (
            <span className="truncate text-neutral-400" title={diag.suggestedAction}>
              → {diag.suggestedAction}
            </span>
          )}
        </div>
      )}
      {/* clicks on the padding land here, not on xterm's screen — forward focus */}
      <div
        ref={mountRef}
        data-terminal-mount
        onClick={() => termRef.current?.focus()}
        className="min-h-0 flex-1 bg-[#0a0a0a] px-2 py-1"
      />
    </section>
  );
}
