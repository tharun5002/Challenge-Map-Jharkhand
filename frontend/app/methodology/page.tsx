import Link from "next/link";
import { AlertTriangle, Database, FileCheck2, FlaskConical, ShieldCheck, Target } from "lucide-react";
import { Badge, ButtonLink } from "@/components/ui";

export const metadata = { title: "Methodology · ChallengeMap" };

const SOURCES = [
  {
    name: "Jharkhand PGMS (Urban Development & Housing)",
    url: "pgms.dmajharkhand.in",
    status: "Reference only",
    note: "Public portal handles single complaints; no bulk export or public list endpoint. Used to mirror real categories and phrasing.",
  },
  {
    name: "DFCA PGMS (Food & Public Distribution)",
    url: "pgms.dfcajharkhand.in",
    status: "Reference only",
    note: "Hindi/English grievance lodgement for PDS issues. No downloadable corpus.",
  },
  {
    name: "Jharkhand MyGov — Public Grievances group",
    url: "jharkhand.mygov.in",
    status: "Illustrative",
    note: "24 public comments only. Useful as real examples in the report, not as a dataset.",
  },
  {
    name: "CPGRAMS / DARPG reports",
    url: "darpg.gov.in",
    status: "Context statistics",
    note: "State and district-wise grievance counts and the Grievance Redressal Index. No raw complaint text.",
  },
  {
    name: "Citizen Grievance Dataset (CC0, Kaggle)",
    url: "kaggle.com",
    status: "Planned benchmark",
    note: "Not downloaded into this repository, so no real-text comparison is reported. Every measured number is synthetic-only.",
  },
  {
    name: "Synthetic corpus (this project)",
    url: "generated",
    status: "Development corpus",
    note: "15,000 seeded records across all 24 districts with injected duplicates and ground-truth labels.",
  },
];

export default function MethodologyPage() {
  return (
    <div className="shell py-10 sm:py-14">
      <div className="max-w-3xl">
        <p className="eyebrow">Methodology</p>
        <h1 className="h1 mt-2 text-3xl sm:text-4xl lg:text-5xl">
          What this system does, and what it does not
        </h1>
        <p className="lede mt-4">
          Written so that a reviewer can check every claim. Nothing here is asserted without a
          dataset, a baseline, or an explicit caveat.
        </p>
      </div>

      <nav className="mt-8 flex flex-wrap gap-2">
        {[
          { href: "#data", label: "Data sources" },
          { href: "#pipeline", label: "Pipeline" },
          { href: "#metrics", label: "Evaluation" },
          { href: "#limits", label: "Limitations" },
          { href: "#ethics", label: "Ethics & PII" },
        ].map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-medium text-fg-soft transition hover:border-teal/40 hover:text-fg"
          >
            {item.label}
          </Link>
        ))}
      </nav>

      {/* Data */}
      <section id="data" className="mt-12 scroll-mt-24">
        <div className="flex items-center gap-2">
          <Database className="h-5 w-5 text-teal" aria-hidden />
          <h2 className="h2 text-2xl">Data sources and what we could actually get</h2>
        </div>
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-fg-soft">
          There is no openly downloadable corpus of Jharkhand citizen complaints. That is a finding,
          not a convenience: every official portal was checked. The project therefore separates what
          is real, what is borrowed, and what is generated.
        </p>

        <div className="mt-6 overflow-x-auto rounded-2xl border border-line bg-surface shadow-card">
          <table className="w-full min-w-[46rem] text-left text-sm">
            <thead className="bg-surface-2 text-[11px] uppercase tracking-wider text-fg-subtle">
              <tr>
                <th className="px-5 py-3 font-semibold">Source</th>
                <th className="px-5 py-3 font-semibold">Use</th>
                <th className="px-5 py-3 font-semibold">What it gives</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {SOURCES.map((source) => (
                <tr key={source.name}>
                  <td className="px-5 py-3">
                    <p className="font-medium text-fg">{source.name}</p>
                    <p className="text-[11px] text-fg-subtle">{source.url}</p>
                  </td>
                  <td className="px-5 py-3">
                    <Badge tone={source.status === "Development corpus" ? "amber" : "neutral"}>
                      {source.status}
                    </Badge>
                  </td>
                  <td className="max-w-md px-5 py-3 text-xs leading-relaxed text-fg-soft">
                    {source.note}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-4 rounded-xl border border-amber/25 bg-amber-soft/50 p-4">
          <p className="flex items-start gap-2 text-xs leading-relaxed text-fg-strong">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber" aria-hidden />
            <span>
              <strong>Demo content is synthetic; live briefs are not a survey.</strong> The
              24-district grid, featured challenges and fallback pages are seeded demo content.
              Briefs served by the API count only reports submitted to this local database, which
              is not a sample of Jharkhand. Neither may be cited as evidence about real communities.
            </span>
          </p>
        </div>
      </section>

      {/* Pipeline */}
      <section id="pipeline" className="mt-14 scroll-mt-24">
        <div className="flex items-center gap-2">
          <FlaskConical className="h-5 w-5 text-teal" aria-hidden />
          <h2 className="h2 text-2xl">Pipeline</h2>
        </div>

        <ol className="mt-6 grid gap-4 md:grid-cols-2">
          {[
            {
              title: "1 · Normalisation",
              body: "Unicode NFC, Devanagari preserved, Hinglish tokens handled, digits and emoji stripped, script detected.",
            },
            {
              title: "2 · Embeddings",
              body: "The multilingual SBERT path (paraphrase-multilingual-MiniLM-L12-v2) is implemented but not installed in this environment. Every measured number comes from the TF-IDF word/char baselines instead.",
            },
            {
              title: "3 · Deduplication",
              body: "Exact sparse TF-IDF cosine against the top-5 neighbours in the same district; the threshold is chosen by an F1 sweep (0.85, F1 0.743).",
            },
            {
              title: "4 · Clustering",
              body: "K-Means, Agglomerative and HDBSCAN are all measured (docs/RESULTS.md); the API re-cluster job uses K-Means because it was not the case that HDBSCAN won on this corpus.",
            },
            {
              title: "5 · Priority scoring",
              body: "Weighted index: severity 30%, affected population 25%, complaint volume 20%, district spread 15%, recurrence 10%. Weights live in config and are sensitivity-tested.",
            },
            {
              title: "6 · Partner matching",
              body: "Capability-tag overlap 40%, district proximity 25%, severity alignment 20%, partner capacity 15%. The breakdown is stored, not just the score.",
            },
          ].map((step) => (
            <li key={step.title} className="card p-5">
              <p className="text-sm font-bold tracking-tight text-fg">{step.title}</p>
              <p className="mt-2 text-sm leading-relaxed text-fg-soft">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Metrics */}
      <section id="metrics" className="mt-14 scroll-mt-24">
        <div className="flex items-center gap-2">
          <Target className="h-5 w-5 text-teal" aria-hidden />
          <h2 className="h2 text-2xl">Evaluation protocol</h2>
        </div>
        <p className="mt-3 max-w-3xl text-sm leading-relaxed text-fg-soft">
          Intrinsic scores alone cannot tell you whether the topics are right, so the plan reports
          agreement against labels as well. Numbers are filled in only after they are measured.
        </p>

        <div className="mt-6 overflow-x-auto rounded-2xl border border-line bg-surface shadow-card">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="bg-surface-2 text-[11px] uppercase tracking-wider text-fg-subtle">
              <tr>
                <th className="px-5 py-3 font-semibold">Question</th>
                <th className="px-5 py-3 font-semibold">Metric</th>
                <th className="px-5 py-3 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line text-fg-soft">
              {[
                ["Does clustering recover the true issue groups?", "ARI, NMI, purity", "ARI 0.253 mixed / 0.442 English slice"],
                ["Does it agree with human judgement?", "Cohen's κ on 300 labelled rows", "Not measured (needs two annotators)"],
                ["Is deep learning worth it over TF-IDF?", "ARI / NMI, TF-IDF vs SBERT", "SBERT path not installed; no comparison"],
                ["Does deduplication catch real repeats?", "Precision, recall, F1", "F1 0.743 at threshold 0.85"],
                ["Is the matching layer useful?", "Precision@5, 50 manual reviews", "Not measured"],
                ["Do clusters separate cleanly?", "Silhouette, Davies–Bouldin", "Measured; supporting only"],
              ].map(([question, metric, status]) => (
                <tr key={question}>
                  <td className="px-5 py-3 text-[13px]">{question}</td>
                  <td className="px-5 py-3 text-[13px] font-medium text-fg">{metric}</td>
                  <td className="px-5 py-3">
                    <Badge tone="amber">{status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Limits */}
      <section id="limits" className="mt-14 scroll-mt-24">
        <div className="flex items-center gap-2">
          <FileCheck2 className="h-5 w-5 text-teal" aria-hidden />
          <h2 className="h2 text-2xl">Known limitations</h2>
        </div>
        <ul className="mt-5 space-y-3">
          {[
            "The development corpus is synthetic. Structure is realistic and duplicates are injected deliberately, but the phrasing distribution is not real citizen language.",
            "No official Jharkhand extract has been granted. A request to NIC Jharkhand / UD&H is part of the plan, and the outcome will be reported either way.",
            "District geography is schematic in this build. A verified 24-district boundary file replaces the grid before any choropleth is published.",
            "Priority weights are a documented judgement, not a validated policy instrument. Sensitivity analysis is mandatory before quoting a ranking.",
            "Measured numbers come from TF-IDF baselines. The multilingual SBERT path is implemented but was not installed here, so no quality or latency comparison exists yet.",
            "Synthetic rows are flagged at the row level and in the interface. They are never presented as verified community evidence.",
          ].map((limit) => (
            <li key={limit} className="flex gap-3 rounded-xl border border-line bg-surface p-4">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber" aria-hidden />
              <p className="text-sm leading-relaxed text-fg-soft">{limit}</p>
            </li>
          ))}
        </ul>
      </section>

      {/* Ethics */}
      <section id="ethics" className="mt-14 scroll-mt-24">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-teal" aria-hidden />
          <h2 className="h2 text-2xl">Ethics, privacy and provenance</h2>
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div className="card p-5">
            <p className="text-sm font-bold">PII handling</p>
            <p className="mt-2 text-sm leading-relaxed text-fg-soft">
              The bulk ingestion path strips phone numbers, emails and ID patterns before storage.
              API submissions are not automatically scrubbed: the form warns citizens not to include
              names, phone numbers or ID numbers, and public evidence quotes never show usernames.
            </p>
          </div>
          <div className="card p-5">
            <p className="text-sm font-bold">Provenance</p>
            <p className="mt-2 text-sm leading-relaxed text-fg-soft">
              Every row carries a <code className="rounded bg-surface-3 px-1">source_type</code> value:
              synthetic, public_dataset, consent_survey or other. The corpus manifest records
              generator version, seed, licence and retrieval date for each source.
            </p>
          </div>
          <div className="card p-5">
            <p className="text-sm font-bold">What the system will not do</p>
            <p className="mt-2 text-sm leading-relaxed text-fg-soft">
              It does not rank districts as &ldquo;worst&rdquo;, does not infer individual
              locations, and does not auto-merge complaints without review. Cluster labels are
              screening aids reviewed by an administrator.
            </p>
          </div>
          <div className="card p-5">
            <p className="text-sm font-bold">Licensing</p>
            <p className="mt-2 text-sm leading-relaxed text-fg-soft">
              The bundled state outline is derived from OpenStreetMap relation 1960191 under ODbL
              1.0, as recorded in the GeoJSON properties. No scraped portal content is redistributed,
              and the planned CC0 benchmark has not been downloaded.
            </p>
          </div>
        </div>
      </section>

      <section className="mt-14 rounded-2xl bg-ink p-8 text-white">
        <h2 className="h2 text-white">Want the full design document?</h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-white/65">
          The master plan records the audit, the ten-week phase order, the database schema, the API
          contract and the evaluation protocol.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <ButtonLink href="/challenges" variant="inverse">
            Browse challenges
          </ButtonLink>
          <ButtonLink
            href="/submit"
            variant="ghost"
            className="border border-white/20 text-white hover:bg-surface/10"
          >
            Report an issue
          </ButtonLink>
        </div>
      </section>
    </div>
  );
}
