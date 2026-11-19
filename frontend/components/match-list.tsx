import { Building2, Check, Clock, Handshake } from "lucide-react";
import type { PartnerMatch } from "@/lib/types";
import { cn } from "@/lib/utils";

const statusMeta: Record<
  PartnerMatch["status"],
  { label: string; className: string; icon: typeof Check }
> = {
  confirmed: { label: "Confirmed", className: "bg-teal/10 text-teal-deep border-teal/25", icon: Check },
  interested: {
    label: "Expressed interest",
    className: "bg-amber/10 text-amber border-amber/25",
    icon: Handshake,
  },
  suggested: { label: "Suggested", className: "bg-fg/5 text-fg-soft border-line-strong", icon: Clock },
  declined: { label: "Declined", className: "bg-fg/5 text-fg-subtle border-line", icon: Clock },
};

export function MatchList({ matches }: { matches: PartnerMatch[] }) {
  if (matches.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-line-strong p-6 text-sm text-fg-subtle">
        No partner matches yet. Run the matching job from the admin console once capability tags
        are assigned.
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {matches.map((match) => {
        const meta = statusMeta[match.status];
        const StatusIcon = meta.icon;
        return (
          <li key={match.organization} className="card p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-fg/5 text-fg-strong">
                  <Building2 className="h-5 w-5" aria-hidden />
                </span>
                <div>
                  <p className="text-sm font-bold leading-snug text-fg">{match.organization}</p>
                  <p className="mt-0.5 text-xs text-fg-subtle">
                    {match.type} · {match.district}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold",
                    meta.className,
                  )}
                >
                  <StatusIcon className="h-3 w-3" aria-hidden />
                  {meta.label}
                </span>
                <span className="rounded-lg bg-ink px-2.5 py-1 text-xs font-bold text-white">
                  {match.score.toFixed(2)}
                </span>
              </div>
            </div>

            <ul className="mt-4 grid gap-2 sm:grid-cols-2">
              {match.reasons.map((reason) => (
                <li key={reason.label} className="rounded-lg bg-surface-2 px-3 py-2">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                    {reason.label}
                  </p>
                  <p className="text-xs leading-snug text-fg-strong">{reason.detail}</p>
                </li>
              ))}
            </ul>
          </li>
        );
      })}
    </ul>
  );
}
