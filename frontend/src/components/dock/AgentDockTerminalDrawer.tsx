import TerminalPane from "../TerminalPane";

/** Provider-scoped PTY drawer — a real terminal without leaving the dock. The
 *  session itself lives on the backend and survives the drawer closing. */
export default function AgentDockTerminalDrawer({ provider }: { provider: string }) {
  return (
    <div className="flex h-64 shrink-0 flex-col">
      <TerminalPane provider={provider} compact />
    </div>
  );
}
