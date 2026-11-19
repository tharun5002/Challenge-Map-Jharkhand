import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  CalendarDays,
  MapPin,
  MessageSquare,
  Quote,
  Users,
} from "lucide-react";
import { getChallenge } from "@/lib/data";
import { fetchChallengeDetail, fetchChallengeMatches } from "@/lib/api";
import { toChallenge } from "@/lib/challenge-view";
import { formatNumber } from "@/lib/utils";
import { PriorityBreakdown } from "@/components/priority-breakdown";
import { MatchList } from "@/components/match-list";
import { Badge, ButtonLink, PriorityPill, SeverityBadge } from "@/components/ui";

export const dynamic = "force-dynamic";

function displayDate(value: string): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-IN", { month: "short", year: "numeric" });
}

export default async function ChallengeDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const [detail, liveMatches] = await Promise.all([
    fetchChallengeDetail(slug),
    fetchChallengeMatches(slug),
  ]);
  const challenge = detail ? toChallenge(detail, liveMatches) : getChallenge(slug);
  if (!challenge) notFound();

  const live = detail !== null;
  const maxTimeline = Math.max(
    1,
    ...challenge.timeline.map((point) => point.complaints),
  );

  return (
    <div className="shell py-8 sm:py-12">
      <Link
        href="/challenges"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-fg-muted transition hover:text-fg"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        All challenges
      </Link>

      <div className="mt-6 grid gap-8 lg:grid-cols-[1.65fr_1fr] lg:items-start">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="teal">{challenge.domain}</Badge>
            <SeverityBadge severity={challenge.severity} />
            <Badge>
              {challenge.status === "published" ? "Published challenge" : "Under review"}
            </Badge>
            {live ? (
              <Badge tone="teal">Live API brief</Badge>
            ) : (
              <Badge tone="amber">Seeded demo dataset</Badge>
            )}
          </div>

          <h1 className="mt-4 text-balance text-3xl font-extrabold leading-[1.1] tracking-[-0.025em] sm:text-4xl">
            {challenge.title}
          </h1>

          <p className="mt-4 text-pretty text-base leading-relaxed text-fg-soft">
            {challenge.summary}
          </p>

          <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Meta
              icon={MessageSquare}
              label="Reports"
              value={formatNumber(challenge.complaintCount)}
            />
            <Meta icon={MapPin} label="Districts" value={String(challenge.districtCount)} />
            <Meta
              icon={Users}
              label="Affected"
              value={formatNumber(challenge.affectedTotal)}
            />
            <Meta
              icon={CalendarDays}
              label="Active since"
              value={displayDate(challenge.firstSeen)}
            />
          </dl>

          {/* Evidence */}
          <section className="mt-10">
            <h2 className="text-lg font-bold tracking-tight">
              What citizens actually wrote
            </h2>
            <p className="mt-1 text-sm text-fg-muted">
              Representative reports from the cluster. Names and contact details are
              stripped on ingest.
            </p>
            {challenge.evidence.length === 0 ? (
              <p className="mt-4 rounded-2xl border border-dashed border-line-strong p-6 text-sm text-fg-subtle">
                No evidence quotes are linked to this brief yet. They appear once
                reports are clustered and the challenge is regenerated.
              </p>
            ) : (
              <div className="mt-4 space-y-3">
                {challenge.evidence.map((item) => (
                  <blockquote
                    key={`${item.district}-${item.date}-${item.quote.slice(0, 24)}`}
                    className="rounded-2xl border border-line bg-surface p-5 shadow-card"
                  >
                    <Quote className="h-4 w-4 text-teal/60" aria-hidden />
                    <p
                      lang={item.language === "Hindi" ? "hi" : "en"}
                      className="mt-2 text-pretty text-[15px] leading-relaxed text-fg"
                    >
                      {item.quote}
                    </p>
                    <footer className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-fg-subtle">
                      <span className="font-semibold text-fg-soft">
                        {item.district}
                      </span>
                      <span aria-hidden>·</span>
                      <span>{item.date}</span>
                      <span aria-hidden>·</span>
                      <span className="rounded-full bg-surface-3 px-2 py-0.5">
                        {item.language}
                      </span>
                    </footer>
                  </blockquote>
                ))}
              </div>
            )}
          </section>

          {/* Trend */}
          <section className="mt-10">
            <h2 className="text-lg font-bold tracking-tight">Reporting trend</h2>
            <p className="mt-1 text-sm text-fg-muted">
              Monthly complaint volume across all affected districts.
            </p>
            {challenge.timeline.length === 0 ? (
              <p className="mt-4 rounded-2xl border border-dashed border-line-strong p-6 text-sm text-fg-subtle">
                No monthly trend yet — it is computed from the dates of the linked
                reports.
              </p>
            ) : (
              <div className="mt-5 rounded-2xl border border-line bg-surface p-5 shadow-card">
                <div className="flex h-40 items-end gap-2 sm:gap-4">
                  {challenge.timeline.map((point) => (
                    <div
                      key={point.month}
                      className="flex flex-1 flex-col items-center gap-2"
                    >
                      <span className="text-[10px] font-semibold text-fg-subtle">
                        {point.complaints}
                      </span>
                      <div
                        className="w-full rounded-t-md bg-gradient-to-t from-teal to-teal-bright transition-all hover:from-teal-deep"
                        style={{
                          height: `${Math.max(
                            8,
                            (point.complaints / maxTimeline) * 100,
                          )}%`,
                        }}
                        title={`${point.month}: ${point.complaints} reports`}
                      />
                      <span className="text-[10px] font-medium text-fg-muted">
                        {point.month}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <p className="mt-2 text-xs text-fg-subtle">
              Live briefs count reports the API actually holds. The seeded demo
              briefs model seasonality; it is not inferred from real data.
            </p>
          </section>

          {/* Districts */}
          {challenge.districts.length > 0 ? (
            <section className="mt-10">
              <h2 className="text-lg font-bold tracking-tight">Where it is reported</h2>
              <ul className="mt-4 divide-y divide-line rounded-2xl border border-line bg-surface shadow-card">
                {challenge.districts.map((district) => (
                  <li
                    key={district.name}
                    className="flex items-center justify-between gap-4 px-5 py-3"
                  >
                    <span className="text-sm font-medium text-fg">{district.name}</span>
                    <div className="flex flex-1 items-center gap-3">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-fg/10">
                        <div
                          className="h-full rounded-full bg-teal"
                          style={{
                            width: `${
                              (district.complaints /
                                Math.max(1, challenge.districts[0].complaints)) *
                              100
                            }%`,
                          }}
                        />
                      </div>
                      <span className="w-10 text-right text-xs font-semibold text-fg-soft">
                        {district.complaints || "—"}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {/* Matches */}
          <section className="mt-10">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <h2 className="text-lg font-bold tracking-tight">Who can solve this</h2>
                <p className="mt-1 text-sm text-fg-muted">
                  Ranked by capability overlap, proximity, severity and capacity.
                </p>
              </div>
              <Link
                href="/partners"
                className="text-sm font-semibold text-teal hover:underline"
              >
                All partners
              </Link>
            </div>
            <div className="mt-4">
              <MatchList matches={challenge.matches} />
            </div>
          </section>
        </div>

        {/* Sidebar */}
        <aside className="space-y-4 lg:sticky lg:top-24">
          <div className="card p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-fg">Take this challenge up</p>
              <PriorityPill score={challenge.priorityScore} />
            </div>
            <p className="mt-2 text-xs leading-relaxed text-fg-muted">
              Partner organisations can express interest and be connected with the
              district administration.
            </p>
            <ButtonLink href="/partners/dashboard" className="mt-4 w-full">
              I can help with this
            </ButtonLink>
            <ButtonLink href="/submit" variant="secondary" className="mt-2 w-full">
              Report a related issue
            </ButtonLink>
          </div>

          {challenge.priorityFactors.length > 0 ? (
            <PriorityBreakdown
              factors={challenge.priorityFactors}
              score={challenge.priorityScore}
            />
          ) : null}

          <div className="card p-5">
            <p className="eyebrow">Tags</p>
            {challenge.tags.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {challenge.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-line bg-surface-2 px-2.5 py-1 text-[11px] font-medium text-fg-soft"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-[11px] text-fg-subtle">
                No capability tags assigned yet.
              </p>
            )}
            <p className="mt-4 text-[11px] leading-relaxed text-fg-subtle">
              Last report {challenge.lastSeen || "not recorded"} ·{" "}
              {challenge.complaintCount} reports collapsed from near-duplicates
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Meta({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof MapPin;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-line bg-surface px-3 py-2.5">
      <dt className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
        <Icon className="h-3 w-3" aria-hidden />
        {label}
      </dt>
      <dd className="mt-1 text-sm font-bold text-fg">{value}</dd>
    </div>
  );
}
