import Link from "next/link";
import {
  ArrowRight,
  BellRing,
  Building2,
  CheckCircle2,
  Layers,
  MapPin,
  MessageSquare,
  Sparkles,
  Users,
} from "lucide-react";
import {
  CHALLENGES,
  DISTRICTS,
  PARTNERS,
  TOTAL_COMPLAINTS,
  TOTAL_CRITICAL,
} from "@/lib/data";
import { formatCompact, formatNumber } from "@/lib/utils";
import { ChallengeCard } from "@/components/challenge-card";
import { DistrictHeatmap } from "@/components/district-heatmap";
import { Badge, ButtonLink, SectionHeading, SeverityBadge, TextLink } from "@/components/ui";

export default function HomePage() {
  const featured = CHALLENGES.slice(0, 3);
  const top = CHALLENGES[0];

  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden bg-ink text-white">
        <div className="absolute inset-0 grid-pattern" aria-hidden />
        <div
          className="absolute -right-32 -top-40 h-[34rem] w-[34rem] rounded-full bg-teal/25 blur-3xl"
          aria-hidden
        />
        <div
          className="absolute -bottom-52 left-1/3 h-[26rem] w-[26rem] rounded-full bg-teal-bright/10 blur-3xl"
          aria-hidden
        />

        <div className="shell relative grid gap-14 py-16 sm:py-20 lg:grid-cols-[1.15fr_0.85fr] lg:py-24">
          <div className="animate-fade-up">
            <Badge tone="teal" className="border-white/15 bg-surface/5 text-teal-bright">
              <Sparkles className="h-3.5 w-3.5" aria-hidden />
              Jharkhand · societal challenge discovery
            </Badge>

            <h1 className="h1 mt-5 text-white">
              Every complaint is a signal.
              <br />
              <span className="text-teal-bright">We turn them into challenges</span> worth
              solving.
            </h1>

            <p className="mt-6 max-w-xl text-pretty text-base leading-relaxed text-white/70 sm:text-lg">
              ChallengeMap groups similar citizen reports into ranked challenge briefs, then
              matches each one to the university departments, labs, NGOs and agencies that can
              actually act on it.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <ButtonLink href="/challenges" variant="inverse" className="px-5 py-3">
                Browse challenges
                <ArrowRight className="h-4 w-4" aria-hidden />
              </ButtonLink>
              <ButtonLink
                href="/submit"
                variant="ghost"
                className="border border-white/20 px-5 py-3 text-white hover:bg-surface/10"
              >
                <MessageSquare className="h-4 w-4" aria-hidden />
                Report an issue
              </ButtonLink>
            </div>

            <dl className="mt-10 grid max-w-lg grid-cols-3 gap-5 border-t border-white/10 pt-6">
              <div>
                <dt className="text-xs text-white/50">Reports clustered</dt>
                <dd className="mt-1 text-2xl font-extrabold tracking-tight">
                  {formatNumber(TOTAL_COMPLAINTS)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-white/50">Districts covered</dt>
                <dd className="mt-1 text-2xl font-extrabold tracking-tight">
                  {DISTRICTS.length}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-white/50">Partner organisations</dt>
                <dd className="mt-1 text-2xl font-extrabold tracking-tight">
                  {PARTNERS.length}
                </dd>
              </div>
            </dl>
          </div>

          {/* Challenge brief preview */}
          <div className="animate-fade-up lg:pt-6">
            <div className="rounded-2xl border border-white/12 bg-surface/[0.06] p-1.5 backdrop-blur">
              <div className="rounded-xl bg-canvas p-5 text-fg shadow-lift">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-fg-subtle">
                    Challenge brief · #{top.slug.slice(0, 4).toUpperCase()}
                  </span>
                  <span className="rounded-full bg-crimson/10 px-2 py-0.5 text-[11px] font-bold text-crimson">
                    Priority {top.priorityScore}
                  </span>
                </div>

                <h2 className="mt-3 text-lg font-extrabold leading-snug tracking-tight">
                  {top.title}
                </h2>

                <div className="mt-3 flex flex-wrap gap-2">
                  <SeverityBadge severity={top.severity} />
                  <Badge tone="teal">
                    <MapPin className="h-3 w-3" aria-hidden />
                    {top.district} +{top.districtCount - 1}
                  </Badge>
                </div>

                <div className="mt-4 grid grid-cols-3 gap-2 rounded-xl bg-surface p-3 text-center">
                  <div>
                    <p className="text-lg font-extrabold leading-none">
                      {top.complaintCount}
                    </p>
                    <p className="mt-1 text-[10px] text-fg-subtle">reports</p>
                  </div>
                  <div className="border-x border-line">
                    <p className="text-lg font-extrabold leading-none">
                      {formatCompact(top.affectedTotal)}
                    </p>
                    <p className="mt-1 text-[10px] text-fg-subtle">affected</p>
                  </div>
                  <div>
                    <p className="text-lg font-extrabold leading-none">{top.matches.length}</p>
                    <p className="mt-1 text-[10px] text-fg-subtle">matches</p>
                  </div>
                </div>

                <div className="mt-4 space-y-2">
                  {top.matches.slice(0, 2).map((match) => (
                    <div
                      key={match.organization}
                      className="flex items-center justify-between gap-2 rounded-lg border border-line bg-surface px-3 py-2"
                    >
                      <span className="flex items-center gap-2 truncate text-xs font-medium text-fg-strong">
                        <Building2 className="h-3.5 w-3.5 shrink-0 text-fg-subtle" aria-hidden />
                        <span className="truncate">{match.organization}</span>
                      </span>
                      <span className="shrink-0 text-xs font-bold text-teal">
                        {match.score.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>

                <Link
                  href={`/challenges/${top.slug}`}
                  className="mt-4 flex items-center justify-center gap-1.5 rounded-lg bg-ink px-3 py-2.5 text-xs font-semibold text-white transition hover:bg-ink-700"
                >
                  Open full brief
                  <ArrowRight className="h-3.5 w-3.5" aria-hidden />
                </Link>
              </div>
            </div>
            <p className="mt-3 text-center text-[11px] text-white/40">
              Illustrative brief · synthetic demo data
            </p>
          </div>
        </div>
      </section>

      {/* Alerts band */}
      <section className="border-b border-line bg-canvas">
        <div className="shell flex flex-wrap items-center justify-between gap-4 py-4">
          <p className="inline-flex items-center gap-2 text-sm text-fg-soft">
            <BellRing className="h-4 w-4 text-amber" aria-hidden />
            <span>
              <strong className="font-semibold text-fg">{formatNumber(TOTAL_CRITICAL)}</strong>{" "}
              reports classified critical this quarter
            </span>
          </p>
          <div className="flex items-center gap-2">
            <Badge>Data pipeline: UI demo</Badge>
            <Badge tone="amber">Synthetic dataset</Badge>
          </div>
        </div>
      </section>

      {/* District intensity */}
      <section className="shell py-16 sm:py-20">
        <SectionHeading
          eyebrow="Where the pressure is"
          title="Complaint intensity across all 24 districts"
          description="Every district is represented, including those with few reports. The grid is schematic — it shows volume, not geography."
          action={<TextLink href="/challenges">Explore by district</TextLink>}
        />
        <div className="mt-8">
          <DistrictHeatmap districts={DISTRICTS} />
        </div>
      </section>

      {/* Featured challenges */}
      <section className="border-y border-line bg-surface-2">
        <div className="shell py-16 sm:py-20">
          <SectionHeading
            eyebrow="Ranked by citizens, not by guesswork"
            title="Challenges open for partnership"
            description="Each brief carries its complaint evidence, affected population and the exact factors behind its priority score."
            action={<TextLink href="/challenges">See all {CHALLENGES.length}</TextLink>}
          />
          <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {featured.map((challenge) => (
              <ChallengeCard key={challenge.slug} challenge={challenge} />
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="shell py-16 sm:py-20">
        <SectionHeading
          eyebrow="How ChallengeMap works"
          title="Four steps from scattered reports to a solvable brief"
        />
        <ol className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[
            {
              icon: MessageSquare,
              title: "1 · Citizens report",
              body: "A complaint is submitted in Hindi, English or Hinglish, with district and severity.",
            },
            {
              icon: Layers,
              title: "2 · Duplicates merge",
              body: "Multilingual embeddings compare the report with existing ones, so the same problem is counted once.",
            },
            {
              icon: CheckCircle2,
              title: "3 · Clusters rank",
              body: "Similar reports become a challenge, scored on severity, population, volume, spread and recurrence.",
            },
            {
              icon: Building2,
              title: "4 · Partners match",
              body: "Capability tags, proximity and capacity produce an explainable match score for each institution.",
            },
          ].map((step) => (
            <li key={step.title} className="card p-5">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-teal/10 text-teal">
                <step.icon className="h-5 w-5" aria-hidden />
              </span>
              <h3 className="mt-4 text-sm font-bold tracking-tight">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-fg-soft">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Matching strip */}
      <section className="bg-ink text-white">
        <div className="shell grid gap-10 py-16 sm:py-20 lg:grid-cols-2 lg:items-center">
          <div>
            <p className="eyebrow text-teal-bright">The part everyone skips</p>
            <h2 className="h2 mt-2 text-white">
              A challenge is only useful if someone can pick it up
            </h2>
            <p className="mt-4 text-pretty text-white/65">
              Most clustering projects stop at a label. ChallengeMap carries the cluster all the
              way to a named institution, with the reasoning exposed: which capability tags
              matched, how far the partner sits from the affected districts, and how much
              capacity they have.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <ButtonLink href="/partners" variant="inverse">
                <Users className="h-4 w-4" aria-hidden />
                Partner directory
              </ButtonLink>
              <ButtonLink
                href="/methodology"
                variant="ghost"
                className="border border-white/20 text-white hover:bg-surface/10"
              >
                Read the methodology
              </ButtonLink>
            </div>
          </div>

          <div className="rounded-2xl border border-white/12 bg-surface/[0.06] p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/40">
              Match explanation
            </p>
            <p className="mt-3 text-sm font-semibold text-white">
              Water & sanitation cluster → Civil Engineering, BIT Mesra
            </p>
            <div className="mt-4 space-y-3">
              {[
                { label: "Capability overlap", value: 0.94 },
                { label: "District proximity", value: 0.81 },
                { label: "Severity alignment", value: 0.9 },
                { label: "Partner capacity", value: 0.62 },
              ].map((row) => (
                <div key={row.label}>
                  <div className="flex justify-between text-xs text-white/60">
                    <span>{row.label}</span>
                    <span className="font-semibold text-white">{row.value.toFixed(2)}</span>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface/10">
                    <div
                      className="h-full rounded-full bg-teal-bright"
                      style={{ width: `${row.value * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-4 rounded-lg bg-black/20 px-3 py-2 text-xs text-white/60">
              Final score 0.86 · reviewed by an administrator before it reaches the partner
            </p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="shell py-16 sm:py-20">
        <div className="card flex flex-wrap items-center justify-between gap-6 bg-teal/5 p-8">
          <div className="max-w-xl">
            <h2 className="h2">Have a problem no one has counted yet?</h2>
            <p className="mt-2 text-fg-soft">
              Report it once. If others already did, we will show you their reports and merge
              yours into the same challenge instead of creating noise.
            </p>
          </div>
          <ButtonLink href="/submit" className="px-5 py-3">
            Report an issue
            <ArrowRight className="h-4 w-4" aria-hidden />
          </ButtonLink>
        </div>
      </section>
    </>
  );
}
