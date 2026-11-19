import type { PriorityFactor } from "@/lib/types";
import { ProgressBar } from "@/components/ui";

/**
 * Shows how a priority score is composed. The point is that a reader can audit
 * the number instead of trusting it — each factor exposes its weight and the
 * evidence behind its value.
 */
export function PriorityBreakdown({
  factors,
  score,
}: {
  factors: PriorityFactor[];
  score: number;
}) {
  return (
    <div className="card p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Priority score</p>
          <p className="mt-1 flex items-baseline gap-1.5">
            <span className="text-4xl font-extrabold tracking-tight">{score}</span>
            <span className="text-sm font-medium text-fg-subtle">/ 100</span>
          </p>
        </div>
        <p className="max-w-[15rem] text-right text-xs leading-relaxed text-fg-subtle">
          Weighted index over five factors. Weights are configuration, not code, and are
          sensitivity-tested in Phase 4.
        </p>
      </div>

      <dl className="mt-6 space-y-4">
        {factors.map((factor) => (
          <div key={factor.label}>
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-sm font-semibold text-fg">{factor.label}</dt>
              <dd className="text-xs font-medium text-fg-subtle">
                weight {(factor.weight * 100).toFixed(0)}% · value {Math.round(factor.value * 100)}
              </dd>
            </div>
            <ProgressBar
              value={factor.value}
              tone={factor.value >= 0.9 ? "crimson" : factor.value >= 0.7 ? "amber" : "teal"}
              className="mt-2"
            />
            <p className="mt-1.5 text-xs text-fg-subtle">{factor.note}</p>
          </div>
        ))}
      </dl>
    </div>
  );
}
