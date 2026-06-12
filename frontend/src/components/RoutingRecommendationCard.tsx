import type { Recommendation } from "../types";
import { ArrowRight } from "./icons";
import { Card } from "./ui";

export default function RoutingRecommendationCard({ rec }: { rec: Recommendation }) {
  return (
    <Card
      title="Routing recommendation"
      pad
      actions={
        <>
          {rec.cheaperRouteRecommended && (
            <span className="rounded-md bg-emerald-100 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
              cheaper route
            </span>
          )}
          {rec.manualApprovalRecommended && (
            <span className="rounded-md bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
              manual approval
            </span>
          )}
        </>
      }
    >
      {rec.warnings.map((w, i) => (
        <div
          key={i}
          className="mb-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300"
        >
          {w}
        </div>
      ))}

      <ul className="space-y-1.5">
        {rec.lines.map((line, i) => (
          <li key={i} className="flex gap-2 text-xs text-neutral-600 dark:text-neutral-400">
            <ArrowRight className="mt-0.5 h-3 w-3 shrink-0 text-accent-subtle" />
            {line}
          </li>
        ))}
      </ul>
    </Card>
  );
}
