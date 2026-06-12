import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import BudgetModePicker from "../components/BudgetModePicker";
import RoutingRecommendationCard from "../components/RoutingRecommendationCard";
import StatusBadge from "../components/StatusBadge";
import UsageHealthBadge from "../components/UsageHealthBadge";
import type { Health, OrchestrationMode, Recommendation, Usage } from "../types";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-[11px] text-neutral-500 dark:text-neutral-400">{label}</div>
      <div className="font-mono text-sm tabular-nums text-neutral-700 dark:text-neutral-300">{value}</div>
    </div>
  );
}

export default function UsagePage() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [u, r] = await Promise.all([api.usage(), api.recommendations()]);
      setUsage(u);
      setRec(r);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const setMode = async (mode: OrchestrationMode) => {
    setUsage(await api.setMode(mode));
    setRec(await api.recommendations());
  };

  const setHealth = async (provider: string, health: Health) => {
    setUsage(await api.setProviderHealth(provider, health));
    setRec(await api.recommendations());
  };

  if (error) {
    return (
      <div className="p-8">
        <h1 className="mb-2 text-xl font-semibold">Usage</h1>
        <p className="text-sm text-amber-600 dark:text-amber-400">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-5 p-8">
      <header>
        <h1 className="text-xl font-semibold">Usage</h1>
        <p className="text-sm text-neutral-500">
          Approximate, subscription-first tracking. Set health manually when a provider hits its quota.
        </p>
      </header>

      {usage && (
        <>
          <section>
            <h2 className="label">Orchestration mode</h2>
            <BudgetModePicker value={usage.orchestrationMode} onChange={(m) => void setMode(m)} />
          </section>

          <section className="grid gap-4 lg:grid-cols-3">
            {Object.entries(usage.providers).map(([id, p]) => (
              <div key={id} className="card p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-sm font-semibold capitalize">{id}</span>
                  <UsageHealthBadge value={p.health} onChange={(h) => void setHealth(id, h)} name={id} />
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                  <Stat label="Calls today" value={p.callsToday} />
                  <Stat label="Budget level" value={p.manualBudgetLevel} />
                  <Stat label="Prompt chars" value={p.estimatedPromptChars.toLocaleString()} />
                  <Stat label="Output chars" value={p.estimatedOutputChars.toLocaleString()} />
                  <Stat label="Last duration" value={`${(p.lastCommandDuration / 1000).toFixed(1)}s`} />
                  <div>
                    <div className="text-[11px] text-neutral-500 dark:text-neutral-400">Last status</div>
                    <StatusBadge state={p.lastStatus} />
                  </div>
                </div>
                <div className="mt-3 border-t border-neutral-100 pt-2 text-[11px] text-neutral-400 dark:border-neutral-800">
                  preferred: {p.preferredUse}
                </div>
              </div>
            ))}
          </section>

          <section className="card flex items-center gap-10 p-4">
            <Stat label="Expensive calls avoided" value={usage.expensiveCallsAvoided} />
            <Stat label="Local steps completed" value={usage.localStepsCompleted} />
            <Stat label="Billing mode" value={usage.mode} />
            <button className="btn-secondary ml-auto" onClick={load}>Refresh</button>
          </section>
        </>
      )}

      {rec && <RoutingRecommendationCard rec={rec} />}
    </div>
  );
}
