"use client";

import { useEffect, useMemo, useState } from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";
import { CHALLENGES, JHARKHAND_DISTRICT_NAMES } from "@/lib/data";
import { fetchPublishedChallenges } from "@/lib/api";
import { toChallengeCard } from "@/lib/challenge-view";
import { ChallengeCard } from "@/components/challenge-card";
import { Badge } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { Challenge, Domain, Severity } from "@/lib/types";

const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];
const SORTS = [
  { id: "priority", label: "Priority" },
  { id: "reports", label: "Most reported" },
  { id: "affected", label: "Largest reach" },
  { id: "recent", label: "Recently active" },
] as const;

export default function ChallengesPage() {
  const [items, setItems] = useState<Challenge[] | null>(null);
  const [source, setSource] = useState<"api" | "demo">("demo");
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState<Domain | "all">("all");
  const [district, setDistrict] = useState<string>("all");
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [sort, setSort] = useState<(typeof SORTS)[number]["id"]>("priority");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const live = await fetchPublishedChallenges();
      if (cancelled) return;
      if (live && live.length > 0) {
        setItems(live.map(toChallengeCard));
        setSource("api");
      } else {
        setItems(CHALLENGES);
        setSource("demo");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const challenges = items ?? [];

  const domains = useMemo(
    () => Array.from(new Set(challenges.map((item) => item.domain))).sort(),
    [challenges],
  );

  const results = useMemo(() => {
    const filtered = challenges.filter((challenge) => {
      const matchesQuery =
        query.trim().length === 0 ||
        `${challenge.title} ${challenge.summary} ${challenge.tags.join(" ")}`
          .toLowerCase()
          .includes(query.trim().toLowerCase());
      const matchesDomain = domain === "all" || challenge.domain === domain;
      const matchesDistrict =
        district === "all" || challenge.districts.some((d) => d.name === district);
      const matchesSeverity = severity === "all" || challenge.severity === severity;
      return matchesQuery && matchesDomain && matchesDistrict && matchesSeverity;
    });

    return filtered.sort((a, b) => {
      if (sort === "reports") return b.complaintCount - a.complaintCount;
      if (sort === "affected") return b.affectedTotal - a.affectedTotal;
      if (sort === "recent") return b.lastSeen.localeCompare(a.lastSeen);
      return b.priorityScore - a.priorityScore;
    });
  }, [challenges, query, domain, district, severity, sort]);

  const activeFilters = [
    domain !== "all" ? domain : null,
    district !== "all" ? district : null,
    severity !== "all" ? severity : null,
  ].filter(Boolean) as string[];

  function reset() {
    setQuery("");
    setDomain("all");
    setDistrict("all");
    setSeverity("all");
  }

  return (
    <div className="shell py-10 sm:py-14">
      <div className="max-w-3xl">
        <p className="eyebrow">Challenge library</p>
        <h1 className="h1 mt-2 text-3xl sm:text-4xl lg:text-5xl">
          {items === null
            ? "Challenges, ranked and ready to be picked up"
            : `${challenges.length} challenges, ranked and ready to be picked up`}
        </h1>
        <p className="lede mt-4">
          Every cluster here is a group of similar citizen reports, not a manual
          category. Filter by what you can act on.
        </p>
        <div className="mt-4">
          {source === "api" ? (
            <Badge tone="teal">Live API · published clusters</Badge>
          ) : (
            <Badge tone="amber">
              Seeded demo dataset · the API returned no published challenges
            </Badge>
          )}
        </div>
      </div>

      {/* Controls */}
      <div className="mt-8 rounded-2xl border border-line bg-surface p-4 shadow-card">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <label className="relative flex-1">
            <span className="sr-only">Search challenges</span>
            <Search
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle"
              aria-hidden
            />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search title, summary or tag…"
              className="w-full rounded-xl border border-line bg-surface-2 py-2.5 pl-9 pr-3 text-sm outline-none transition focus:border-teal focus:bg-surface"
            />
          </label>

          <div className="flex flex-wrap items-center gap-2">
            <select
              value={district}
              onChange={(event) => setDistrict(event.target.value)}
              className="rounded-xl border border-line bg-surface px-3 py-2.5 text-sm font-medium text-fg-strong outline-none focus:border-teal"
              aria-label="Filter by district"
            >
              <option value="all">All districts</option>
              {JHARKHAND_DISTRICT_NAMES.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>

            <select
              value={sort}
              onChange={(event) => setSort(event.target.value as typeof sort)}
              className="rounded-xl border border-line bg-surface px-3 py-2.5 text-sm font-medium text-fg-strong outline-none focus:border-teal"
              aria-label="Sort challenges"
            >
              {SORTS.map((option) => (
                <option key={option.id} value={option.id}>
                  Sort: {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-3 flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar">
          <SlidersHorizontal className="h-4 w-4 shrink-0 text-fg-subtle" aria-hidden />
          <FilterChip active={domain === "all"} onClick={() => setDomain("all")}>
            All domains
          </FilterChip>
          {domains.map((label) => (
            <FilterChip
              key={label}
              active={domain === label}
              onClick={() => setDomain(domain === label ? "all" : label)}
            >
              {label}
            </FilterChip>
          ))}
        </div>

        <div className="mt-2 flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar">
          <span className="w-4 shrink-0" aria-hidden />
          {SEVERITIES.map((level) => (
            <FilterChip
              key={level}
              active={severity === level}
              onClick={() => setSeverity(severity === level ? "all" : level)}
            >
              <span className="capitalize">{level}</span>
            </FilterChip>
          ))}
          {activeFilters.length > 0 ? (
            <button
              type="button"
              onClick={reset}
              className="ml-1 inline-flex shrink-0 items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold text-crimson hover:bg-crimson/5"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
              Clear
            </button>
          ) : null}
        </div>
      </div>

      <p className="mt-6 text-sm text-fg-subtle" aria-live="polite">
        Showing <strong className="text-fg">{results.length}</strong> of{" "}
        {challenges.length} challenges
      </p>

      {items === null ? (
        <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((index) => (
            <div
              key={index}
              className="h-56 animate-pulse rounded-2xl border border-line bg-surface-2"
              aria-hidden
            />
          ))}
        </div>
      ) : results.length === 0 ? (
        <div className="mt-6 rounded-2xl border border-dashed border-line-strong bg-surface p-12 text-center">
          <p className="text-lg font-semibold">No challenge matches those filters</p>
          <p className="mt-1 text-sm text-fg-muted">
            Try a broader district, or clear the domain chips.
          </p>
          <button
            type="button"
            onClick={reset}
            className="mt-4 rounded-xl bg-ink px-4 py-2 text-sm font-semibold text-white"
          >
            Reset filters
          </button>
        </div>
      ) : (
        <div className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {results.map((challenge) => (
            <ChallengeCard key={challenge.slug} challenge={challenge} />
          ))}
        </div>
      )}
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "shrink-0 rounded-full border px-3 py-1 text-xs font-medium transition",
        active
          ? "border-teal bg-teal text-white"
          : "border-line bg-surface text-fg-soft hover:border-line-strong",
      )}
    >
      {children}
    </button>
  );
}
