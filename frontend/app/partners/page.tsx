import { Building2, MapPin, Sparkles } from "lucide-react";
import { PARTNERS } from "@/lib/data";
import { Badge, ButtonLink, SectionHeading } from "@/components/ui";

export const metadata = { title: "Partners · ChallengeMap" };

export default function PartnersPage() {
  return (
    <div className="shell py-10 sm:py-14">
      <div className="max-w-3xl">
        <p className="eyebrow">Partner network</p>
        <h1 className="h1 mt-2 text-3xl sm:text-4xl lg:text-5xl">
          The institutions that can actually solve these
        </h1>
        <p className="lede mt-4">
          Universities, research labs, NGOs, industry teams and government departments, each with
          declared capability tags. Matching runs against those tags — not against informal
          contacts.
        </p>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {PARTNERS.map((partner) => (
          <article key={partner.name} className="card flex h-full flex-col p-5">
            <div className="flex items-start justify-between gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-fg/5 text-fg-strong">
                <Building2 className="h-5 w-5" aria-hidden />
              </span>
              <Badge tone="teal">{partner.type}</Badge>
            </div>

            <h2 className="mt-3 text-[15px] font-bold leading-snug tracking-tight">
              {partner.name}
            </h2>
            <p className="mt-1 inline-flex items-center gap-1 text-xs text-fg-subtle">
              <MapPin className="h-3 w-3" aria-hidden />
              {partner.district}
            </p>
            <p className="mt-3 flex-1 text-sm leading-relaxed text-fg-soft">{partner.blurb}</p>

            <div className="mt-4 flex flex-wrap gap-1.5">
              {partner.focus.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full bg-surface-3/70 px-2 py-0.5 text-[10px] font-medium text-fg-soft"
                >
                  {tag}
                </span>
              ))}
            </div>

            <p className="mt-4 border-t border-line pt-3 text-xs text-fg-muted">
              <strong className="font-semibold text-fg">{partner.activeChallenges}</strong> active
              challenges
            </p>
          </article>
        ))}
      </div>

      <section className="mt-14 rounded-2xl border border-line bg-surface p-8 shadow-card">
        <SectionHeading
          eyebrow="For organisations"
          title="Declare your capability tags and start receiving briefs"
          description="A partner profile is a list of things you can genuinely do — water-quality testing, school WASH retrofits, process audits — plus your district coverage and current capacity. Matching is transparent: you see exactly why a challenge was routed to you. Partner accounts are issued by the programme administrator; sign in to reach your matched challenges."
          action={
            <ButtonLink href="/login">
              <Sparkles className="h-4 w-4" aria-hidden />
              Partner sign in
            </ButtonLink>
          }
        />
      </section>
    </div>
  );
}
