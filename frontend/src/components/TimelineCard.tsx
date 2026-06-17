import { StepChip } from "./Markdown";
import { Disclosure } from "./TaskViews";
import RawDetail from "./RawDetail";
import { CARD_STYLE, SEVERITY_TEXT, type CardModel } from "../lib/displayModel";

/* The one card renderer shared by the controller dock (compact) and the Tasks
   page (detailed). Driven entirely by a CardModel's DisplayData so the same
   structured state renders identically at two densities — same dot, title,
   provider/step chips, and status. See docs/task-controller-io-surface.md. */

const SPECIAL_ARTIFACTS: Record<string, string> = {
  "@code": "production code",
  "@diff": "git diff",
  "@folder": "task folder",
};

function ArtifactChip({ name, onOpen }: { name: string; onOpen?: (name: string) => void }) {
  const special = SPECIAL_ARTIFACTS[name];
  if (special) {
    return (
      <span className="rounded border border-violet-200 bg-violet-50 px-1.5 py-0.5 font-mono text-[10px] text-violet-700 dark:border-violet-900 dark:bg-violet-950/40 dark:text-violet-300">
        {special}
      </span>
    );
  }
  return (
    <button
      onClick={() => onOpen?.(name)}
      disabled={!onOpen}
      title={onOpen ? `Open ${name}` : name}
      className={`focusable rounded border border-emerald-300 bg-emerald-50 px-1.5 py-0.5 font-mono text-[10px] text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 ${
        onOpen ? "cursor-pointer hover:border-blue-400 hover:text-blue-600" : ""
      }`}
    >
      {name.replace(".md", "")}
    </button>
  );
}

export default function TimelineCard({
  card,
  density = "detailed",
  onOpenArtifact,
}: {
  card: CardModel;
  density?: "compact" | "detailed";
  onOpenArtifact?: (name: string) => void;
}) {
  const style = CARD_STYLE[card.type];
  const d = card.display;
  const time = d.timestamp ? new Date(d.timestamp).toLocaleTimeString() : "";

  if (density === "compact") {
    return (
      <div className="flex items-start gap-2">
        <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${style.dot}`} aria-hidden="true" />
        {time && (
          <span className="w-16 shrink-0 font-mono text-[10px] tabular-nums leading-5 text-neutral-400">{time}</span>
        )}
        <div className="min-w-0 flex-1 text-xs leading-5 text-neutral-700 dark:text-neutral-300">
          <span className={`mr-1.5 font-medium ${SEVERITY_TEXT[d.severity]}`}>{d.title}</span>
          {d.step && <StepChip name={d.step} />}
          {d.provider && <span className="ml-1 font-mono text-[10px] text-neutral-400">{d.provider}</span>}
          {d.summary?.bullets[0] && <span className="ml-1.5">{d.summary.bullets[0]}</span>}
          {(d.artifacts ?? []).length > 0 && (
            <span className="ml-1.5 inline-flex flex-wrap gap-1 align-middle">
              {d.artifacts!.map((a) => (
                <ArtifactChip key={a} name={a} onOpen={onOpenArtifact} />
              ))}
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={`card border-l-2 ${style.accent} p-2.5`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${style.dot}`} aria-hidden="true" />
        <span className={`text-xs font-semibold ${SEVERITY_TEXT[d.severity]}`}>{d.title}</span>
        {d.step && <StepChip name={d.step} />}
        {d.provider && <span className="chip">{d.provider}</span>}
        <span className="flex-1" />
        {time && <span className="font-mono text-[10px] tabular-nums text-neutral-400">{time}</span>}
      </div>

      {d.summary && d.summary.bullets.length > 0 && (
        <ul className="mt-1.5 space-y-0.5">
          {d.summary.bullets.slice(0, 5).map((b, i) => (
            <li key={i} className="text-xs leading-snug text-neutral-700 dark:text-neutral-300">
              {b}
            </li>
          ))}
        </ul>
      )}

      {(d.artifacts ?? []).length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {d.artifacts!.map((a) => (
            <ArtifactChip key={a} name={a} onOpen={onOpenArtifact} />
          ))}
        </div>
      )}

      {(d.rawDetail ?? []).map((r, i) => (
        <Disclosure key={i} label={r.label} className="mt-1.5">
          <RawDetail text={r.text ?? ""} kind={r.kind} label={r.label} />
        </Disclosure>
      ))}
    </div>
  );
}
