import { useCallback, useEffect, useRef, useState } from "react";
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { api } from "../api";
import { AntigravityMark, ClaudeMark, OpenAIMark } from "../components/icons";

/* Three real PTY terminals — codex, claude, antigravity — each a live
   interactive shell (with the CLI auto-launched) streamed over a WebSocket.
   Output is rendered by xterm.js, so ANSI colors and TUIs work; keystrokes and
   resizes flow back to the pty. Sessions live on the backend and survive tab
   switches, so a running CLI keeps going while you're elsewhere. */

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

function wsUrl(provider: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/api/terminals/${provider}/ws`;
}

function TerminalPane({ provider, installed }: { provider: string; installed: boolean }) {
  const meta = META[provider] ?? { name: provider, icon: null };
  const mountRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<number | null>(null);
  const [connected, setConnected] = useState(false);
  const [epoch, setEpoch] = useState(0); // bump to reconnect / restart the session

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
      setConnected(true);
      doFit();
      ws.send(JSON.stringify({ type: "resize", rows: term.rows, cols: term.cols }));
    };
    ws.onmessage = (ev) => {
      if (ev.data instanceof ArrayBuffer) term.write(new Uint8Array(ev.data));
      else term.write(ev.data as string);
    };
    // Unexpected drops (e.g. the backend restarted) leave a dead pane otherwise:
    // xterm still takes keystrokes but they go nowhere. Auto-reconnect so the
    // session self-heals. Intentional teardown nulls onclose first (see cleanup),
    // so this only fires on real drops.
    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = window.setTimeout(() => setEpoch((e) => e + 1), 1500);
    };
    ws.onerror = () => setConnected(false);

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
    setEpoch((e) => e + 1); // tear down and start a fresh session
  }, [provider]);

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-800">
      <header className="flex shrink-0 items-center gap-2 border-b border-neutral-800 bg-neutral-900 px-3 py-1.5">
        <span className="flex items-center gap-1.5 text-neutral-300">
          {meta.icon}
          <span className="text-xs font-semibold">{meta.name}</span>
        </span>
        {!installed && (
          <span className="rounded border border-amber-900 bg-amber-950/40 px-1.5 py-0.5 text-[10px] text-amber-300">
            not installed
          </span>
        )}
        <span className="flex-1" />
        <span className="inline-flex items-center gap-1.5 text-[10px] text-neutral-400">
          <span
            className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-500" : "bg-neutral-600"}`}
            aria-hidden="true"
          />
          {connected ? "connected" : "disconnected"}
        </span>
        <button
          onClick={() => void kill()}
          className="focusable cursor-pointer rounded px-1.5 py-0.5 text-[10px] font-medium text-neutral-400 transition-colors hover:bg-neutral-800 hover:text-rose-400"
          title="Kill and restart this session"
        >
          Restart
        </button>
      </header>
      <div ref={mountRef} className="min-h-0 flex-1 bg-[#0a0a0a] px-2 py-1" />
    </section>
  );
}

export default function TerminalsPage() {
  const [installed, setInstalled] = useState<Record<string, boolean>>({});
  const [providers, setProviders] = useState<string[]>(["codex", "claude", "antigravity"]);

  useEffect(() => {
    void api
      .terminalsStatus()
      .then((s) => {
        setProviders(s.providers);
        setInstalled(s.installed);
      })
      .catch(() => {
        /* backend offline — sidebar already shows it */
      });
  }, []);

  return (
    <div className="flex h-full flex-col">
      <header className="flex shrink-0 items-center gap-2 px-6 pb-2 pt-5">
        <h1 className="text-xl font-semibold">Terminals</h1>
        <span className="text-xs text-neutral-500">
          live CLI sessions · type into them like a real terminal
        </span>
      </header>
      <div className="flex min-h-0 flex-1 flex-col gap-3 px-6 pb-6">
        {providers.map((p) => (
          <TerminalPane key={p} provider={p} installed={installed[p] ?? false} />
        ))}
      </div>
    </div>
  );
}
