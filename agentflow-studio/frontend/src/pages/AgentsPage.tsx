import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import ProviderCard from "../components/ProviderCard";
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

  return (
    <div className="space-y-5 p-8">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">Agents</h1>
          <p className="text-sm text-neutral-500">
            Installed CLI tools. AgentFlow uses each tool's own login — no API keys are stored.
          </p>
        </div>
        <button className="btn-primary" onClick={checkAll} disabled={checkingAll}>
          {checkingAll ? "Checking all…" : "Check All"}
        </button>
      </header>

      {error && <p className="text-sm text-rose-500">{error}</p>}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3">
        {providers.map((p) => (
          <ProviderCard key={p.id} provider={p} onCheck={checkOne} onLogin={login} />
        ))}
        {providers.length === 0 &&
          !error &&
          [0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="skeleton h-56" aria-hidden="true" />)}
      </div>
    </div>
  );
}
