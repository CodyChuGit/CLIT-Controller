import { useEffect, useState } from "react";
import type { Provider } from "../types";
import { ChevronDown, ChevronRight, Spinner } from "./icons";
import StatusBadge from "./StatusBadge";
import UsageHealthBadge from "./UsageHealthBadge";

interface Props {
  provider: Provider;
  onCheck: (id: string) => Promise<void>;
  onLogin: (id: string) => Promise<string>;
  onInstall: (id: string) => Promise<string>;
  onSetModel: (id: string, model: string) => Promise<string>;
}

const CUSTOM = "__custom__";

const DOT: Record<string, string> = {
  ok: "bg-emerald-500",
  needs_login: "bg-amber-500",
  version_unknown: "bg-neutral-400",
  error: "bg-rose-500",
  missing: "bg-rose-400",
  unchecked: "bg-neutral-300 dark:bg-neutral-600",
};

function copyText(text: string) {
  if (navigator.clipboard?.writeText) void navigator.clipboard.writeText(text);
}

/** One agent as a dense, expandable row (VS Code extensions-list style — see DESIGN.md). */
export default function ProviderCard({ provider: p, onCheck, onLogin, onInstall, onSetModel }: Props) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const [customMode, setCustomMode] = useState(false);
  const [customModel, setCustomModel] = useState("");

  useEffect(() => {
    setCustomMode(false);
    setCustomModel("");
  }, [p.model]);

  const run = async (fn: () => Promise<string | void>) => {
    setBusy(true);
    setNote(null);
    try {
      const msg = await fn();
      if (msg) setNote(msg);
    } catch (e) {
      setNote(String(e));
    } finally {
      setBusy(false);
    }
  };

  const saveModel = async (next: string) => {
    if (next.trim() === (p.model ?? "")) return;
    await run(() => onSetModel(p.id, next.trim()));
  };

  const dotState = p.installing ? "bg-blue-500 animate-pulse" : DOT[p.installed ? p.status : "missing"] ?? DOT.unchecked;

  return (
    <div className="border-b border-neutral-200 last:border-0 dark:border-neutral-800">
      {/* main row */}
      <div className="flex items-center gap-2.5 px-3 py-2">
        <span className={`h-2 w-2 shrink-0 rounded-full ${dotState}`} title={p.installed ? p.status : "not installed"} aria-hidden="true" />
        <button
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
          className="focusable flex min-w-0 cursor-pointer items-center gap-1.5 rounded text-left"
        >
          {expanded ? (
            <ChevronDown className="h-3 w-3 shrink-0 text-neutral-400" />
          ) : (
            <ChevronRight className="h-3 w-3 shrink-0 text-neutral-400" />
          )}
          <span className="truncate text-xs font-semibold">{p.displayName}</span>
        </button>
        <span className="hidden truncate font-mono text-[11px] text-neutral-400 sm:inline" title={p.version ?? ""}>
          {p.version ?? ""}
        </span>

        <span className="flex-1" />

        {p.installing && (
          <span className="flex items-center gap-1.5 text-[11px] text-blue-600 dark:text-blue-400">
            <Spinner className="h-3 w-3" /> installing…
          </span>
        )}
        {!p.installed && !p.installing && (
          <button
            onClick={() => void run(() => onInstall(p.id))}
            disabled={busy}
            title={p.installCommand ? `Install now: ${p.installCommand}` : p.installHint}
            aria-label={`Install ${p.displayName}`}
            className="focusable cursor-pointer rounded-full transition-transform duration-150 hover:scale-105 active:scale-95"
          >
            <StatusBadge state="missing" label="not installed · install" />
          </button>
        )}

        {p.modelEditable && p.installed && (
          customMode ? (
            <input
              id={`model-${p.id}`}
              autoFocus
              className="input w-40 px-2 py-0.5 font-mono text-[11px]"
              placeholder="model name…"
              value={customModel}
              onChange={(e) => setCustomModel(e.target.value)}
              onBlur={() => {
                if (customModel.trim()) void saveModel(customModel);
                setCustomMode(false);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                if (e.key === "Escape") setCustomMode(false);
              }}
            />
          ) : (
            <select
              id={`model-${p.id}`}
              aria-label={`${p.displayName} model`}
              className="input w-40 cursor-pointer px-2 py-0.5 font-mono text-[11px]"
              value={p.model ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                if (v === CUSTOM) {
                  setCustomModel(p.model ?? "");
                  setCustomMode(true);
                } else {
                  void saveModel(v);
                }
              }}
            >
              <option value="">CLI default</option>
              {p.model && !p.modelOptions.includes(p.model) && <option value={p.model}>{p.model}</option>}
              {p.modelOptions.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
              <option value={CUSTOM}>Custom…</option>
            </select>
          )
        )}

        {p.usageHealth && <UsageHealthBadge value={p.usageHealth} name={p.id} />}

        <button className="btn-secondary btn-xs" onClick={() => void run(() => onCheck(p.id))} disabled={busy || p.installing}>
          {busy ? <Spinner className="h-3 w-3" /> : "Check"}
        </button>
        {p.loginCommand && p.installed && (
          <button className="btn-secondary btn-xs" onClick={() => void run(() => onLogin(p.id))} disabled={busy}>
            Login
          </button>
        )}
      </div>

      {note && (
        <p className="px-9 pb-2 text-[11px] text-amber-700 dark:text-amber-400">{note}</p>
      )}

      {/* expanded detail */}
      {expanded && (
        <div className="border-t border-neutral-100 bg-neutral-50/60 px-9 py-2.5 dark:border-neutral-800 dark:bg-neutral-950/60">
          <dl className="grid grid-cols-1 gap-x-8 gap-y-1 text-[11px] sm:grid-cols-2">
            {[
              ["Executables", p.executableNames.join(", "), true],
              ["Path", p.executablePath ?? "—", true],
              ["Auth", p.authMode, false],
              ["Usage mode", p.usageMode, false],
              ["Preferred use", p.preferredUse, false],
              ["Calls today", String(p.callsToday ?? 0), false],
              ["Last checked", p.lastChecked ? new Date(p.lastChecked).toLocaleTimeString() : "never", false],
              ["Login command", p.loginCommand ?? "—", true],
            ].map(([label, value, mono]) => (
              <div key={label as string} className="flex justify-between gap-3">
                <dt className="shrink-0 text-neutral-500 dark:text-neutral-400">{label}</dt>
                <dd className={`truncate text-right text-neutral-700 dark:text-neutral-300 ${mono ? "font-mono" : ""}`} title={value as string}>
                  {value}
                </dd>
              </div>
            ))}
          </dl>

          {!p.installed && (
            <p className="mt-2 rounded-md bg-amber-50 px-2.5 py-1.5 text-[11px] text-amber-800 dark:bg-amber-950/50 dark:text-amber-300">
              Install: <code className="font-mono">{p.installHint}</code>
            </p>
          )}

          <div className="mt-2 flex flex-wrap gap-1.5">
            <button
              className="btn-secondary btn-xs"
              onClick={() => {
                copyText(p.loginCommand ?? p.versionCommand);
                setNote(`Copied: ${p.loginCommand ?? p.versionCommand}`);
              }}
            >
              Copy command
            </button>
            {p.lastLog && (
              <button className="btn-secondary btn-xs" onClick={() => setShowLog(!showLog)} aria-expanded={showLog}>
                {showLog ? "Hide log" : "Last log"}
              </button>
            )}
          </div>
          {showLog && p.lastLog && <pre className="mono-block mt-2 max-h-44 whitespace-pre-wrap text-[10px]">{p.lastLog}</pre>}
        </div>
      )}
    </div>
  );
}
