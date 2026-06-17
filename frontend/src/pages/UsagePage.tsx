import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import BudgetModePicker from "../components/BudgetModePicker";
import { Refresh } from "../components/icons";
import RoutingRecommendationCard from "../components/RoutingRecommendationCard";
import { Loading, PageShell } from "../components/ui";
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

/** One aligned row per CLI-reported window: label · bar (fill = remaining) · % left · reset. */
function QuotaCell({ liveData, loading }: { liveData?: LiveProviderUsage; loading?: boolean }) {
  const windows = liveData?.available ? (liveData.windows ?? []) : [];
  if (loading) {
    return (
      <div className="flex items-center gap-2.5 text-[11px]">
        <span className="w-16 shrink-0" aria-hidden="true" />
        <span className="skeleton h-1.5 min-w-0 flex-1" />
        <span className="w-16 shrink-0" aria-hidden="true" />
        <span className="w-28 shrink-0" aria-hidden="true" />
      </div>
    );
  }
  if (windows.length === 0) {
    return (
      <div className="flex items-center gap-2.5 text-[11px]">
        <span className="w-16 shrink-0" aria-hidden="true" />
        <span className="font-mono text-neutral-400">NA</span>
      </div>
    );
  }
  return (
    <div className="space-y-1.5" title="Live from the CLI">
      {windows.map((w) => {
        const left = Math.max(0, 100 - w.usedPercent);
        return (
          <div key={w.label} className="flex items-center gap-2.5 text-[11px]">
            <span className="w-16 shrink-0 truncate text-right font-mono text-[10px] text-neutral-400">
              {w.label}
            </span>
            <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800">
              <div
                className={`h-full rounded-full ${pctColor(w.usedPercent)}`}
                style={{ width: `${Math.min(100, left)}%` }}
              />
            </div>
            <span
              className={`w-16 shrink-0 text-right font-semibold tabular-nums ${
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
              className="w-28 shrink-0 truncate text-right tabular-nums text-neutral-400"
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
    // Base usage + recommendations are cheap; render the table from them right
    // away. Live quota shells out to each CLI (slow, 120s-cached) — fetch it
    // separately so the cells show their own loading state meanwhile.
    try {
      const [u, r] = await Promise.all([api.usage(), api.recommendations()]);
      setUsage(u);
      setRec(r);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return;
    }
    try {
      setLive(await api.usageLive());
    } catch {
      setLive({}); // clear the loading state; cells fall back to "NA"
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
      <PageShell title="Usage">
        <p className="text-sm text-amber-600 dark:text-amber-400">{error}</p>
      </PageShell>
    );
  }

  return (
    <PageShell
      title="Usage"
      actions={
        <button
          onClick={() => void load()}
          title="Refresh"
          aria-label="Refresh usage"
          className="icon-btn"
        >
          <Refresh className="h-3.5 w-3.5" />
        </button>
      }
    >
      {!usage && <Loading label="Loading usage…" />}

      {usage && (
        <>
          <div className="flex items-center gap-3">
            <span className="label">Traffic control</span>
            <BudgetModePicker value={usage.orchestrationMode} onChange={(m) => void setMode(m)} />
          </div>

          <section className="card overflow-hidden">
            <table className="w-full table-fixed text-xs">
              <colgroup>
                <col className="w-44" />
                <col className="w-28" />
                <col />
              </colgroup>
              <thead>
                <tr className="border-b border-neutral-200 text-left text-[10px] uppercase tracking-wide text-neutral-400 dark:border-neutral-800">
                  <th className="px-3 py-1.5 font-semibold">Provider</th>
                  <th className="px-2 py-1.5 font-semibold">Health</th>
                  <th className="px-3 py-1.5 font-semibold">
                    <div className="flex items-center gap-2.5">
                      <span className="w-16 shrink-0" aria-hidden="true" />
                      <span className="min-w-0 flex-1">Session quota</span>
                      <span className="shrink-0">Resets</span>
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(usage.providers).map(([id, p]) => (
                  <tr
                    key={id}
                    className="border-b border-neutral-100 last:border-0 dark:border-neutral-800/60"
                  >
                    <td className="px-3 py-2.5">
                      <div className="truncate font-mono font-semibold">{id}</div>
                      <div className="truncate text-[10px] text-neutral-400">
                        {p.preferredUse}
                        {live?.[id]?.plan ? ` · ${live[id].plan}` : ""}
                      </div>
                    </td>
                    <td className="px-2 py-2.5">
                      <UsageHealthBadge
                        value={p.health}
                        onChange={(h) => void setHealth(id, h)}
                        name={id}
                      />
                    </td>
                    <td className="px-3 py-2.5">
                      <QuotaCell liveData={live?.[id]} loading={live === null} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <p className="text-[11px] text-neutral-500">
            {usage.localStepsCompleted} local steps · {usage.expensiveCallsAvoided} expensive calls
            avoided
          </p>
        </>
      )}

      {rec && <RoutingRecommendationCard rec={rec} />}
    </PageShell>
  );
}
