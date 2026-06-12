import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { Spinner } from "../components/icons";
import ProviderCard from "../components/ProviderCard";
import { Card, PageShell } from "../components/ui";
import type { Provider } from "../types";

export default function AgentsPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [checkingAll, setCheckingAll] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setProviders(await api.agents());
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // While any one-click install is running, poll so cards flip to "installed" on their own.
  const anyInstalling = providers.some((p) => p.installing);
  useEffect(() => {
    if (!anyInstalling) return;
    const id = window.setInterval(load, 3000);
    return () => window.clearInterval(id);
  }, [anyInstalling, load]);

  const checkOne = async (id: string) => {
    const updated = await api.checkAgent(id);
    setProviders((prev) => prev.map((p) => (p.id === id ? updated : p)));
  };

  const checkAll = async () => {
    setCheckingAll(true);
    try {
      setProviders(await api.checkAllAgents());
    } catch (e) {
      setError(String(e));
    } finally {
      setCheckingAll(false);
    }
  };

  const login = async (id: string) => {
    const res = await api.loginAgent(id);
    return res.message;
  };

  const install = async (id: string) => {
    const res = await api.installAgent(id);
    await load();
    if (res.status === "started") {
      return `Installing in the background: ${res.command}`;
    }
    return res.message ?? res.status;
  };

  const setModel = async (id: string, model: string) => {
    const res = await api.setAgentModel(id, model);
    await load();
    return res.model ? `Model set: ${res.model}` : "Model cleared — using the CLI default.";
  };

  return (
    <PageShell
      title="Agents"
      actions={
        <button className="btn-primary" onClick={checkAll} disabled={checkingAll}>
          {checkingAll && <Spinner className="h-3.5 w-3.5" />}
          {checkingAll ? "Checking…" : "Check All"}
        </button>
      }
    >
      {error && <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>}

      <Card title={`Installed CLIs${providers.length > 0 ? ` (${providers.length})` : ""}`}>
        {providers.map((p) => (
          <ProviderCard
            key={p.id}
            provider={p}
            onCheck={checkOne}
            onLogin={login}
            onInstall={install}
            onSetModel={setModel}
          />
        ))}
        {providers.length === 0 && !error && (
          <div className="space-y-2 p-3" aria-hidden="true">
            {[0, 1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="skeleton h-7" />
            ))}
          </div>
        )}
      </Card>
    </PageShell>
  );
}
