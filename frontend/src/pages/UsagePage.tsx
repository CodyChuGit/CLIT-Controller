import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import BudgetModePicker from "../components/BudgetModePicker";
import { Refresh } from "../components/icons";
import RoutingRecommendationCard from "../components/RoutingRecommendationCard";
import StatusBadge from "../components/StatusBadge";
import UsageHealthBadge from "../components/UsageHealthBadge";
import type { Health, LiveProviderUsage, OrchestrationMode, Recommendation, Usage } from "../types";

function fmtDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 90_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms / 60_000)}m${Math.round((ms % 60_000) / 1000)}s`;
}



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

/** Real session usage straight from the CLI's own data. */
function LiveWindows({ liveData }: { liveData: LiveProviderUsage }) {
  return (
    <div className="space-y-1">
      {(liveData.windows ?? []).map((w) => (
        <div key={w.label} className="flex items-center justify-end gap-1.5">
          <span className="font-mono text-[10px] text-neutral-400">{w.label}</span>
          <div className="h-1.5 w-20 overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800">
            <div className={`h-full rounded-full ${pctColor(w.usedPercent)}`} style={{ width: `${Math.min(100, w.usedPercent)}%` }} />
          </div>
          <span className={`w-16 text-right tabular-nums font-semibold ${
            w.usedPercent >= 90 ? "text-rose-600 dark:text-rose-400" : w.usedPercent >= 65 ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400"
          }`}>
            {(100 - w.usedPercent).toFixed(0)}% left
          </span>
        </div>
      ))}
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
        <header>
          <h1 className="text-xl font-semibold">Usage</h1>
        </header>

        {usage && (
          <>
            <section>
              <h2 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                Orchestration mode
              </h2>
              <BudgetModePicker value={usage.orchestrationMode} onChange={(m) => void setMode(m)} />
            </section>

            <section className="card overflow-hidden">
              <div className="flex items-center border-b border-neutral-200 px-3 py-1.5 dark:border-neutral-800">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                  Provider usage
                </span>
                <span className="flex-1" />
                <button
                  onClick={() => void load()}
                  title="Refresh"
                  aria-label="Refresh usage"
                  className="focusable cursor-pointer rounded p-1 text-neutral-400 transition-colors duration-150 hover:bg-neutral-200 hover:text-neutral-700 dark:hover:bg-neutral-700 dark:hover:text-neutral-200"
                >
                  <Refresh className="h-3.5 w-3.5" />
                </button>
              </div>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-neutral-200 text-left text-[10px] uppercase tracking-wide text-neutral-400 dark:border-neutral-800">
                    <th className="px-3 py-1.5 font-semibold">Provider</th>
                    <th className="px-2 py-1.5 font-semibold">Health</th>
                    <th className="px-2 py-1.5 text-right font-semibold">Used / limit</th>
                    <th className="px-2 py-1.5 font-semibold">Resets</th>
                    <th className="px-2 py-1.5 text-right font-semibold">Chars in / out</th>
                    <th className="px-2 py-1.5 text-right font-semibold">Last run</th>
                    <th className="px-3 py-1.5 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(usage.providers).map(([id, p]) => (
                    <tr key={id} className="border-b border-neutral-100 last:border-0 dark:border-neutral-800/60">
                      <td className="px-3 py-1.5">
                        <div className="font-mono font-semibold">{id}</div>
                        <div className="text-[10px] text-neutral-400">{p.preferredUse}</div>
                      </td>
                      <td className="px-2 py-1.5">
                        <UsageHealthBadge value={p.health} onChange={(h) => void setHealth(id, h)} name={id} />
                      </td>
                      <td className="px-2 py-1.5 text-right">
                        {live?.[id]?.available ? (
                          <LiveWindows liveData={live[id]} />
                        ) : (
                          <span className="text-neutral-400">NA</span>
                        )}
                      </td>
                      <td className="px-2 py-1.5">
                        {live?.[id]?.available ? (
                          <div className="space-y-0.5">
                            {(live[id].windows ?? []).map((w) => (
                              <div key={w.label} className="flex items-center gap-1.5 text-[11px]">
                                <span className="font-mono text-[10px] text-neutral-400">{w.label}</span>
                                <span className="tabular-nums text-neutral-500">{w.resetsText ?? epochResets(w.resetsAt)}</span>
                              </div>
                            ))}
                            <span className="rounded bg-violet-100 px-1 text-[9px] font-semibold uppercase text-violet-700 dark:bg-violet-950 dark:text-violet-300">
                              live{live[id].plan ? ` · ${live[id].plan}` : ""}
                            </span>
                          </div>
                        ) : (
                          <span className="text-neutral-400">NA</span>
                        )}
                      </td>
                      <td className="px-2 py-1.5 text-right tabular-nums">
                        {p.estimatedPromptChars.toLocaleString()} / {p.estimatedOutputChars.toLocaleString()}
                      </td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{fmtDuration(p.lastCommandDuration)}</td>
                      <td className="px-3 py-1.5">
                        <StatusBadge state={p.lastStatus} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex flex-wrap items-center gap-x-6 gap-y-1 border-t border-neutral-200 px-3 py-2 text-[11px] text-neutral-500 dark:border-neutral-800">
                <span>
                  Expensive calls avoided{" "}
                  <span className="font-mono tabular-nums text-neutral-700 dark:text-neutral-300">
                    {usage.expensiveCallsAvoided}
                  </span>
                </span>
                <span>
                  Local steps completed{" "}
                  <span className="font-mono tabular-nums text-neutral-700 dark:text-neutral-300">
                    {usage.localStepsCompleted}
                  </span>
                </span>
                <span>
                  Billing <span className="font-mono text-neutral-700 dark:text-neutral-300">{usage.mode}</span>
                </span>
              </div>
            </section>
          </>
        )}

        {rec && <RoutingRecommendationCard rec={rec} />}
      </div>
    </div>
  );
}
