import { useEffect, useRef, useState } from "react";
import { ComposerChip } from "../Composer";
import InputComposer from "../input/InputComposer";
import { ProviderMark } from "../conversation/Message";
import { ChevronDown } from "../icons";
import type { ChatSendResult, Usage } from "../../types";
import { HEALTH_DOT, MODE_LABELS } from "./AgentDockFooter";

/** Controller engine picker with brand marks — native selects can't render SVGs. */
function EngineSelect({
  value,
  options,
  onChange,
}: {
  value: string;
  options: { id: string; installed: boolean }[];
  onChange: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        onClick={() => setOpen(!open)}
        title="CLI that runs the controller"
        aria-label="Controller CLI"
        aria-haspopup="listbox"
        aria-expanded={open}
        className="focusable flex h-[38px] cursor-pointer items-center gap-1.5 rounded-md border border-neutral-200 bg-white px-2 font-mono text-[10px] text-neutral-600 transition-colors duration-150 hover:border-neutral-300 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-300 dark:hover:border-neutral-600"
      >
        <ProviderMark id={value} className="h-4 w-4" />
        <ChevronDown
          className={`h-3 w-3 text-neutral-400 transition-transform duration-150 ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div
          role="listbox"
          aria-label="Controller CLI options"
          className="absolute bottom-full left-0 z-20 mb-1 w-44 overflow-hidden rounded-md border border-neutral-200 bg-white py-1 shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
        >
          {options.map((p) => (
            <button
              key={p.id}
              role="option"
              aria-selected={p.id === value}
              onClick={() => {
                onChange(p.id);
                setOpen(false);
              }}
              className={`focusable flex w-full cursor-pointer items-center gap-2 px-2.5 py-1.5 text-left font-mono text-[11px] transition-colors duration-150 hover:bg-neutral-100 dark:hover:bg-neutral-800 ${
                p.id === value
                  ? "text-neutral-900 dark:text-neutral-100"
                  : "text-neutral-500 dark:text-neutral-400"
              }`}
            >
              <ProviderMark id={p.id} className="h-3.5 w-3.5" />
              <span className="flex-1">{p.id}</span>
              {!p.installed && <span className="text-[10px] text-neutral-400">not installed</span>}
              {p.id === value && (
                <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden="true" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** The dock composer: notice row + InputComposer wired to the typed submit
 *  plane, with the controller's engine picker and mode/health context chips. */
export default function AgentDockComposer({
  workspacePath,
  isOrch,
  channel,
  selected,
  providers,
  usage,
  pending,
  notice,
  onProviderChange,
  onResult,
  onStop,
}: {
  workspacePath: string | null;
  isOrch: boolean;
  channel: string;
  selected: string;
  providers: { id: string; installed: boolean }[] | undefined;
  usage: Usage | null;
  pending: boolean;
  notice: string | null;
  onProviderChange: (id: string) => void;
  onResult: (res: ChatSendResult) => void;
  onStop?: () => void;
}) {
  const hasWorkspace = Boolean(workspacePath);
  return (
    <div className="shrink-0 border-t border-neutral-200 p-2.5 dark:border-neutral-800">
      {notice && (
        <p className="mb-2 rounded-lg bg-amber-50 px-2.5 py-1.5 text-[11px] text-amber-800 dark:bg-amber-950/50 dark:text-amber-300">
          {notice}
        </p>
      )}
      <InputComposer
        workspaceId={workspacePath ?? "workspace"}
        destination={isOrch ? { kind: "controller" } : { kind: "provider", provider: channel }}
        context={isOrch ? { provider: selected } : undefined}
        onResult={onResult}
        onStop={pending ? onStop : undefined}
        busy={pending}
        disabled={!hasWorkspace}
        placeholder={
          !hasWorkspace
            ? "Open a workspace first"
            : isOrch
              ? "Ask the controller…"
              : `Message ${channel} directly…`
        }
        leading={
          isOrch ? (
            <EngineSelect
              value={selected}
              options={providers ?? [{ id: selected, installed: true }]}
              onChange={onProviderChange}
            />
          ) : undefined
        }
        contextChips={
          isOrch && usage ? (
            <>
              <ComposerChip title="Traffic control mode">
                {MODE_LABELS[usage.orchestrationMode] ?? usage.orchestrationMode}
              </ComposerChip>
              {["codex", "claude", "antigravity"].map((id) =>
                usage.providers[id] ? (
                  <ComposerChip
                    key={id}
                    dot={HEALTH_DOT[usage.providers[id].health] ?? "bg-neutral-400"}
                    mono
                    title={`${id} health`}
                  >
                    {id}
                  </ComposerChip>
                ) : null,
              )}
            </>
          ) : undefined
        }
      />
    </div>
  );
}
