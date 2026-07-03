import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, PageShell } from "../components/ui";
import type { HeadroomStatus, PonytailLevel, RoutingConfig, Settings } from "../types";

const ROLE_LABELS: Record<keyof RoutingConfig, string> = {
  orchestrator: "Controller",
  pm: "PM / Spec / Review",
  engineer: "Engineer",
  qa: "QA",
};

const PROVIDER_OPTIONS = ["codex", "claude", "antigravity"];

const PONYTAIL_LEVELS: { id: PonytailLevel; hint: string }[] = [
  { id: "off", hint: "no shaping" },
  { id: "lite", hint: "the ladder only" },
  { id: "full", hint: "ladder + rules (default)" },
  { id: "ultra", hint: "ruthless minimalism" },
];

function Dot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-neutral-500">
      <span
        className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-500" : "bg-neutral-300 dark:bg-neutral-600"}`}
        aria-hidden="true"
      />
      {label}
    </span>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [routing, setRouting] = useState<RoutingConfig | null>(null);
  const [templates, setTemplates] = useState<Record<string, string>>({});
  const [headroom, setHeadroom] = useState<HeadroomStatus | null>(null);
  const [ponytail, setPonytail] = useState<PonytailLevel>("full");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applySettings = (s: Settings) => {
    setSettings(s);
    setRouting(s.routing);
    setTemplates(s.commandTemplates);
    setHeadroom(s.headroom);
    setPonytail(s.ponytail?.level ?? "full");
  };

  useEffect(() => {
    void api
      .settings()
      .then(applySettings)
      .catch((e) => setError(String(e)));
  }, []);

  const save = async () => {
    setError(null);
    try {
      const s = await api.saveSettings({
        routing: routing ?? undefined,
        commandTemplates: templates,
        headroom: headroom
          ? {
              enabled: headroom.enabled,
              proxyUrl: headroom.proxyUrl,
              savingsProfile: headroom.savingsProfile,
            }
          : undefined,
        ponytail: { level: ponytail },
      });
      applySettings(s);
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
    <PageShell title="Settings">
      <Card title="Routing defaults" pad>
        <div className="grid grid-cols-2 gap-4">
          {(Object.keys(ROLE_LABELS) as (keyof RoutingConfig)[]).map((role) => (
            <div key={role}>
              <label className="label">{ROLE_LABELS[role]}</label>
              <select
                className="input"
                value={routing[role]}
                onChange={(e) => setRouting({ ...routing, [role]: e.target.value })}
              >
                {/* Antigravity is the tool runner, never the router — the
                    backend migrates it off the controller role anyway. */}
                {(role === "orchestrator"
                  ? PROVIDER_OPTIONS.filter((p) => p !== "antigravity")
                  : PROVIDER_OPTIONS
                ).map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </Card>

      {/* The token-management strategy: Headroom compresses what goes INTO the
          models; Ponytail shrinks what comes OUT of the agents. */}
      <Card title="Token savings" pad>
        {headroom && (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={headroom.enabled}
                  onChange={(e) => setHeadroom({ ...headroom, enabled: e.target.checked })}
                />
                <span className="font-medium">Headroom proxy</span>
              </label>
              <span className="text-xs text-neutral-500">
                compresses prompt context (input side) · fail-open
              </span>
              <span className="flex-1" />
              <Dot
                ok={headroom.installed}
                label={headroom.installed ? "installed" : "not installed"}
              />
              <Dot ok={headroom.reachable} label={headroom.reachable ? "proxy up" : "proxy down"} />
              {headroom.managed && <Dot ok label="managed by CLITC" />}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Proxy URL</label>
                <input
                  className="input font-mono"
                  value={headroom.proxyUrl}
                  onChange={(e) => setHeadroom({ ...headroom, proxyUrl: e.target.value })}
                />
              </div>
              <div>
                <label className="label">Savings profile</label>
                <input
                  className="input font-mono"
                  value={headroom.savingsProfile}
                  onChange={(e) => setHeadroom({ ...headroom, savingsProfile: e.target.value })}
                />
              </div>
            </div>
            <p className="text-xs text-neutral-500">
              Routes {headroom.routedProviders.join(" and ")} through the proxy when it is up;
              agents run direct otherwise. Headroom installs with the backend (a Python dependency)
              — CLITC starts and manages the proxy itself.
              {!headroom.installed && (
                <>
                  {" "}
                  Missing here: re-run <code className="font-mono">./scripts/install.sh</code> to
                  refresh backend dependencies.
                </>
              )}
            </p>
          </div>
        )}

        <div className="mt-4 border-t border-neutral-200 pt-3 dark:border-neutral-800">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-medium">Ponytail discipline</span>
            <span className="text-xs text-neutral-500">
              minimalism ladder in every agent prompt (output side)
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {PONYTAIL_LEVELS.map((l) => (
              <label
                key={l.id}
                className={`flex cursor-pointer items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition-colors ${
                  ponytail === l.id
                    ? "border-accent bg-accent/10 text-blue-700 dark:text-blue-300"
                    : "border-neutral-200 text-neutral-500 hover:border-neutral-300 dark:border-neutral-700"
                }`}
              >
                <input
                  type="radio"
                  name="ponytail"
                  className="sr-only"
                  checked={ponytail === l.id}
                  onChange={() => setPonytail(l.id)}
                />
                <span className="font-mono font-medium">{l.id}</span>
                <span className="text-neutral-400">{l.hint}</span>
              </label>
            ))}
          </div>
        </div>
      </Card>

      <Card title="Command templates" pad>
        <p className="mb-3 text-xs text-neutral-500">
          <code className="font-mono">{"{prompt}"}</code> is replaced with the generated prompt
          (passed as a single argument, never through a shell string).
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
      </Card>

      <div className="flex items-center gap-3">
        <button className="btn-primary" onClick={save}>
          Save settings
        </button>
        {saved && <span className="text-xs text-emerald-600 dark:text-emerald-400">Saved ✓</span>}
        {error && <span className="text-xs text-rose-500">{error}</span>}
      </div>

      <Card title="Paths" pad>
        <dl className="space-y-2 text-xs">
          {[
            ["Workspace", settings.workspacePath ?? "not set"],
            ["Global config", settings.globalConfigPath],
            ["Workspace config", settings.workspaceConfigPath ?? "—"],
            ["Usage file", settings.usageFilePath ?? "—"],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4">
              <dt className="shrink-0 text-neutral-400">{label}</dt>
              <dd
                className="truncate font-mono text-neutral-600 dark:text-neutral-400"
                title={value ?? ""}
              >
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </Card>

      <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300">
        CLIT Controller uses official CLI auth and does not store provider secrets.
      </p>
    </PageShell>
  );
}
