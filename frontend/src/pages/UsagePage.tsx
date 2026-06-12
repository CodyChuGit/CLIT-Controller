import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import BudgetModePicker from "../components/BudgetModePicker";
import { Refresh } from "../components/icons";
import RoutingRecommendationCard from "../components/RoutingRecommendationCard";
import UsageHealthBadge from "../components/UsageHealthBadge";
import type { Health, LiveProviderUsage, OrchestrationMode, Recommendation, Usage } from "../types";

function epochResets(resetsAt: number | null): string {
  if (!resetsAt) return "";
  const ms = resetsAt * 1000 - Date.now();
  if (ms <= 0) return "now";
  const h = Math.floor(ms / 3_600_000);
  const m = Math.round((ms % 3_600_000) / 60_000);
  return h > 24 ? `in ${Math.round(h / 24)}d ${h % 24}h` : h > 0 ? `in ${h}h ${m}m` : `in ${m}m`;
}

function pctColor(used: number): string {
  if (used >= 90) return "bg-rose-500";
  if (used >= 65) return "bg-amber-500";
  return "bg-emerald-500";
}

/** One row per CLI-reported window: label · bar · % left · reset. */
function QuotaCell({ liveData }: { liveData?: LiveProviderUsage }) {
  const windows = liveData?.available ? liveData.windows ?? [] : [];
  if (windows.length === 0) return <span className="text-neutral-400">NA</span>;
  return (
    <div className="space-y-1" title="Live from the CLI">
      {windows.map((w) => {
        const left = Math.max(0, 100 - w.usedPercent);
        return (
          <div key={w.label} className="flex items-center justify-end gap-2 text-[11px]">
            <span className="font-mono text-[10px] text-neutral-400">{w.label}</span>
            <div className="h-1.5 w-24 overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800">
              <div
                className={`h-full rounded-full ${pctColor(w.usedPercent)}`}
                style={{ width: `${Math.min(100, w.usedPercent)}%` }}
              />
            </div>
            <span
              className={`w-14 text-right font-semibold tabular-nums ${
                w.usedPercent >= 90
                  ? "text-rose-600 dark:text-rose-400"
                  : w.usedPercent >= 65
                    ? "text-amber-600 dark:text-amber-400"
                    : "text-emerald-600 dark:text-emerald-400"
              }`}
            >
              {left.toFixed(0)}% left
            </span>
            <span
              className="w-24 truncate text-left tabular-nums text-neutral-400"
              title={w.resetsText ?? undefined}
            >
              {(w.resetsText ?? epochResets(w.resetsAt)).replace(/\s*\(.*$/, "")}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function UsagePage() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [live, setLive] = useState<Record<string, LiveProviderUsage> | null>(null);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [u, r, l] = await Promise.all([api.usage(), api.recommendations(), api.usageLive()]);
      setUsage(u);
      setRec(r);
      setLive(l);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
    const id = window.setInterval(load, 60_000);
    return () => window.clearInterval(id);
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
      <div className="p-6">
        <h1 className="mb-2 text-xl font-semibold">Usage</h1>
        <p className="text-sm text-amber-600 dark:text-amber-400">{error}</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-4 p-6">
        <header className="flex items-center">
          <h1 className="text-xl font-semibold">Usage</h1>
          <span className="flex-1" />
          <button onClick={() => void load()} title="Refresh" aria-label="Refresh usage" className="icon-btn">
            <Refresh className="h-3.5 w-3.5" />
          </button>
        </header>

        {usage && (
          <>
            <div className="flex items-center gap-3">
              <span className="label">Mode</span>
              <BudgetModePicker value={usage.orchestrationMode} onChange={(m) => void setMode(m)} />
            </div>

            <section className="card overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-neutral-200 text-left text-[10px] uppercase tracking-wide text-neutral-400 dark:border-neutral-800">
                    <th className="px-3 py-1.5 font-semibold">Provider</th>
                    <th className="px-2 py-1.5 font-semibold">Health</th>
                    <th className="px-3 py-1.5 text-right font-semibold">Session quota</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(usage.providers).map(([id, p]) => (
                    <tr key={id} className="border-b border-neutral-100 last:border-0 dark:border-neutral-800/60">
                      <td className="px-3 py-2">
                        <div className="font-mono font-semibold">{id}</div>
                        <div className="text-[10px] text-neutral-400">
                          {p.preferredUse}
                          {live?.[id]?.plan ? ` · ${live[id].plan}` : ""}
                        </div>
                      </td>
                      <td className="px-2 py-2">
                        <UsageHealthBadge value={p.health} onChange={(h) => void setHealth(id, h)} name={id} />
                      </td>
                      <td className="px-3 py-2">
                        <QuotaCell liveData={live?.[id]} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            <p className="text-[11px] text-neutral-500">
              {usage.localStepsCompleted} local steps · {usage.expensiveCallsAvoided} expensive calls avoided
            </p>
          </>
        )}

        {rec && <RoutingRecommendationCard rec={rec} />}
      </div>
    </div>
  );
}
