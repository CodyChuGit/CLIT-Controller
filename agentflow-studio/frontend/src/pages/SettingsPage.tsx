import { useEffect, useState } from "react";
import { api } from "../api";
import type { RoutingConfig, Settings } from "../types";

const ROLE_LABELS: Record<keyof RoutingConfig, string> = {
  orchestrator: "Orchestrator",
  pm: "PM / Spec / Review",
  engineer: "Engineer",
  qa: "QA",
};

const PROVIDER_OPTIONS = ["codex", "claude", "antigravity"];

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [routing, setRouting] = useState<RoutingConfig | null>(null);
  const [templates, setTemplates] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api.settings().then((s) => {
      setSettings(s);
      setRouting(s.routing);
      setTemplates(s.commandTemplates);
    }).catch((e) => setError(String(e)));
  }, []);

  const save = async () => {
    setError(null);
    try {
      const s = await api.saveSettings(routing, templates);
      setSettings(s);
      setRouting(s.routing);
      setTemplates(s.commandTemplates);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  if (!settings || !routing) {
    return <div className="p-8 text-sm text-neutral-400">{error ?? "Loading settings…"}</div>;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-6">
      <header>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="text-xs text-neutral-500">Routing defaults, command templates, models, and paths.</p>
      </header>

      <section className="card p-5">
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Routing defaults</h2>
        <div className="grid grid-cols-2 gap-4">
          {(Object.keys(ROLE_LABELS) as (keyof RoutingConfig)[]).map((role) => (
            <div key={role}>
              <label className="label">{ROLE_LABELS[role]}</label>
              <select
                className="input"
                value={routing[role]}
                onChange={(e) => setRouting({ ...routing, [role]: e.target.value })}
              >
                {PROVIDER_OPTIONS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </section>

      <section className="card p-5">
        <h2 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Command templates</h2>
        <p className="mb-3 text-xs text-neutral-500">
          <code className="font-mono">{"{prompt}"}</code> is replaced with the generated prompt (passed as a
          single argument, never through a shell string).
        </p>
        <div className="space-y-3">
          {Object.entries(templates).map(([provider, template]) => (
            <div key={provider}>
              <label className="label">{provider}</label>
              <input
                className="input font-mono"
                value={template}
                onChange={(e) => setTemplates({ ...templates, [provider]: e.target.value })}
              />
            </div>
          ))}
        </div>
      </section>

      <div className="flex items-center gap-3">
        <button className="btn-primary" onClick={save}>Save settings</button>
        {saved && <span className="text-xs text-emerald-600 dark:text-emerald-400">Saved ✓</span>}
        {error && <span className="text-xs text-rose-500">{error}</span>}
      </div>

      <section className="card p-5">
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Paths</h2>
        <dl className="space-y-2 text-xs">
          {[
            ["Workspace", settings.workspacePath ?? "not set"],
            ["Global config", settings.globalConfigPath],
            ["Workspace config", settings.workspaceConfigPath ?? "—"],
            ["Usage file", settings.usageFilePath ?? "—"],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4">
              <dt className="shrink-0 text-neutral-400">{label}</dt>
              <dd className="truncate font-mono text-neutral-600 dark:text-neutral-400" title={value ?? ""}>
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300">
        AgentFlow uses official CLI auth and does not store provider secrets.
      </p>
    </div>
  );
}
