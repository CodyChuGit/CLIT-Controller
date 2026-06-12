import { useEffect, useState } from "react";
import type { Provider } from "../types";
import { Spinner } from "./icons";
import StatusBadge from "./StatusBadge";
import UsageHealthBadge from "./UsageHealthBadge";

interface Props {
  provider: Provider;
  onCheck: (id: string) => Promise<void>;
  onLogin: (id: string) => Promise<string>;
  onInstall: (id: string) => Promise<string>;
  onSetModel: (id: string, model: string) => Promise<string>;
}

const MODEL_SUGGESTIONS: Record<string, string[]> = {
  claude: ["sonnet", "opus", "haiku"],
  codex: [],
  antigravity: [],
};

function copyText(text: string) {
  if (navigator.clipboard?.writeText) void navigator.clipboard.writeText(text);
}

export default function ProviderCard({ provider: p, onCheck, onLogin, onInstall, onSetModel }: Props) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [showLog, setShowLog] = useState(false);
  const [model, setModel] = useState(p.model ?? "");

  // Stay in sync when the providers list refreshes externally.
  useEffect(() => setModel(p.model ?? ""), [p.model]);

  const saveModel = async () => {
    const next = model.trim();
    if (next === (p.model ?? "")) return;
    try {
      setNote(await onSetModel(p.id, next));
    } catch (e) {
      setNote(String(e));
    }
  };

  const check = async () => {
    setBusy(true);
    setNote(null);
    try {
      await onCheck(p.id);
    } finally {
      setBusy(false);
    }
  };

  const login = async () => {
    setBusy(true);
    try {
      setNote(await onLogin(p.id));
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  };

  const install = async () => {
    setBusy(true);
    setNote(null);
    try {
      setNote(await onInstall(p.id));
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  };

  const badge = p.installing ? (
    <StatusBadge state="running" label="installing…" />
  ) : p.installed ? (
    <StatusBadge state={p.status} label={p.status === "unchecked" ? "unchecked" : p.status} />
  ) : (
    // One-click install: the "not installed" badge itself is the trigger.
    <button
      onClick={install}
      disabled={busy}
      title={p.installCommand ? `Install now: ${p.installCommand}` : p.installHint}
      aria-label={`Install ${p.displayName}`}
      className="focusable cursor-pointer rounded-full transition-transform duration-150 hover:scale-105 active:scale-95"
    >
      <StatusBadge state="missing" label="not installed · install" />
    </button>
  );

  return (
    <div className="card flex flex-col p-4">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-semibold">{p.displayName}</div>
          <div className="font-mono text-[11px] text-neutral-400">{p.executableNames.join(", ")}</div>
        </div>
        {badge}
      </div>

      <dl className="mb-3 space-y-1 text-xs text-neutral-600 dark:text-neutral-400">
        <div className="flex justify-between gap-2">
          <dt className="text-neutral-500 dark:text-neutral-400">Version</dt>
          <dd className="truncate font-mono" title={p.version ?? ""}>{p.version ?? "—"}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-neutral-500 dark:text-neutral-400">Auth</dt>
          <dd className="truncate text-right">{p.authMode}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-neutral-500 dark:text-neutral-400">Usage mode</dt>
          <dd className="truncate text-right">{p.usageMode}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-neutral-500 dark:text-neutral-400">Preferred use</dt>
          <dd className="truncate text-right" title={p.preferredUse}>{p.preferredUse}</dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-neutral-500 dark:text-neutral-400">Usage health</dt>
          <dd className="flex items-center gap-2">
            {p.usageHealth ? <UsageHealthBadge value={p.usageHealth} name={p.id} /> : <span>—</span>}
            {p.callsToday > 0 && <span className="tabular-nums text-neutral-500">{p.callsToday} calls</span>}
          </dd>
        </div>
        {p.modelEditable && (
          <div className="flex items-center justify-between gap-2">
            <dt className="text-neutral-500 dark:text-neutral-400">
              <label htmlFor={`model-${p.id}`}>Model</label>
            </dt>
            <dd className="min-w-0 flex-1 text-right">
              <input
                id={`model-${p.id}`}
                list={MODEL_SUGGESTIONS[p.id]?.length ? `models-${p.id}` : undefined}
                className="input ml-auto max-w-[170px] px-2 py-0.5 text-right font-mono text-[11px]"
                placeholder="CLI default"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                onBlur={() => void saveModel()}
                onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
              />
              {MODEL_SUGGESTIONS[p.id]?.length > 0 && (
                <datalist id={`models-${p.id}`}>
                  {MODEL_SUGGESTIONS[p.id].map((m) => (
                    <option key={m} value={m} />
                  ))}
                </datalist>
              )}
            </dd>
          </div>
        )}
        <div className="flex justify-between gap-2">
          <dt className="text-neutral-500 dark:text-neutral-400">Last checked</dt>
          <dd>
            {p.lastChecked ? (
              <time dateTime={p.lastChecked} className="tabular-nums">
                {new Date(p.lastChecked).toLocaleTimeString()}
              </time>
            ) : (
              "never"
            )}
          </dd>
        </div>
      </dl>

      {!p.installed && !p.installing && (
        <div className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/50 dark:text-amber-300">
          Install: <code className="font-mono">{p.installHint}</code>
        </div>
      )}
      {p.installing && (
        <div className="mb-3 flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-800 dark:bg-blue-950/50 dark:text-blue-300">
          <Spinner className="h-3.5 w-3.5" />
          Installing in the background — status updates automatically.
        </div>
      )}
      {note && (
        <div className="mb-3 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-800 dark:bg-blue-950/50 dark:text-blue-300">
          {note}
        </div>
      )}

      <div className="mt-auto flex flex-wrap gap-2">
        {!p.installed && !p.installing && p.installCommand && (
          <button className="btn-primary" onClick={install} disabled={busy}>
            Install
          </button>
        )}
        <button className="btn-secondary" onClick={check} disabled={busy || p.installing}>
          {busy && <Spinner className="h-3.5 w-3.5" />}
          {busy ? "Checking…" : "Check"}
        </button>
        {p.loginCommand && (
          <button className="btn-secondary" onClick={login} disabled={busy || !p.installed}>
            Login / Setup
          </button>
        )}
        <button
          className="btn-secondary"
          onClick={() => {
            copyText(p.loginCommand ?? p.versionCommand);
            setNote(`Copied: ${p.loginCommand ?? p.versionCommand}`);
          }}
        >
          Copy command
        </button>
        {p.lastLog && (
          <button className="btn-secondary" onClick={() => setShowLog(!showLog)}>
            {showLog ? "Hide log" : "Log"}
          </button>
        )}
      </div>

      {showLog && p.lastLog && <pre className="mono-block mt-3 max-h-44 whitespace-pre-wrap">{p.lastLog}</pre>}
    </div>
  );
}
