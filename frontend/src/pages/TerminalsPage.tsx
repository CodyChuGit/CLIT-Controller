import { useEffect, useState } from "react";
import { api } from "../api";
import TerminalPane from "../components/TerminalPane";

/* Three real PTY terminals — codex, claude, antigravity — rendered by the
   shared TerminalPane (also used by the Agent Dock terminal drawer). Sessions
   live on the backend and survive tab switches, so a running CLI keeps going
   while you're elsewhere. Each pane shows its launch lifecycle (resolving →
   launching → ready) and explains failures instead of a dead box. */

export default function TerminalsPage() {
  const [providers, setProviders] = useState<string[]>(["codex", "claude", "antigravity"]);

  useEffect(() => {
    void api
      .terminalsStatus()
      .then((s) => setProviders(s.providers))
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
          <TerminalPane key={p} provider={p} />
        ))}
      </div>
    </div>
  );
}
