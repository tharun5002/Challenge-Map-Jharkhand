import Link from "next/link";
import { MapPin, MessageSquare, Users } from "lucide-react";
import type { Challenge } from "@/lib/types";
import { formatCompact, cn } from "@/lib/utils";
import { PriorityPill, SeverityBadge } from "@/components/ui";

const domainAccent: Record<string, string> = {
  "Water & Sanitation": "bg-sky-50 text-sky-800 border-sky-200",
  Healthcare: "bg-rose-50 text-rose-800 border-rose-200",
  Education: "bg-violet-50 text-violet-800 border-violet-200",
  "Roads & Connectivity": "bg-stone-100 text-stone-700 border-stone-200",
  Electricity: "bg-amber-50 text-amber-800 border-amber-200",
  "Food & PDS": "bg-lime-50 text-lime-800 border-lime-200",
  "Welfare & Pensions": "bg-teal-50 text-teal-800 border-teal-200",
  "Land & Revenue": "bg-indigo-50 text-indigo-800 border-indigo-200",
};

export function ChallengeCard({ challenge }: { challenge: Challenge }) {
  return (
    <article className="group relative flex h-full flex-col rounded-2xl border border-line bg-surface p-5 shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-teal/40 hover:shadow-lift">
      <div className="flex items-start justify-between gap-3">
        <span
          className={cn(
            "inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-semibold",
            domainAccent[challenge.domain] ?? "border-line bg-surface-3 text-fg-strong",
          )}
        >
          {challenge.domain}
        </span>
        <PriorityPill score={challenge.priorityScore} />
      </div>

      <h3 className="mt-3 text-[17px] font-bold leading-snug tracking-tight text-fg">
        <Link href={`/challenges/${challenge.slug}`} className="after:absolute after:inset-0">
          {challenge.title}
        </Link>
      </h3>

      <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-fg-soft">{challenge.summary}</p>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-fg-subtle">
        <span className="inline-flex items-center gap-1.5">
          <MessageSquare className="h-3.5 w-3.5" aria-hidden />
          {challenge.complaintCount} reports
        </span>
        <span className="inline-flex items-center gap-1.5">
          <MapPin className="h-3.5 w-3.5" aria-hidden />
          {challenge.districtCount} districts
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Users className="h-3.5 w-3.5" aria-hidden />
          {formatCompact(challenge.affectedTotal)} affected
        </span>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-line pt-3">
        <SeverityBadge severity={challenge.severity} />
        <span className="text-xs font-semibold text-teal transition group-hover:translate-x-0.5">
          View brief →
        </span>
      </div>
    </article>
  );
}
