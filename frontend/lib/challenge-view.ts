/**
 * Adapters from the API payloads to the view models the public pages render.
 *
 * The API stores lexicon domains (`water`, `health`, …) and numeric component
 * scores; the interface speaks in display labels. Keeping that translation in
 * one module means a page never has to know both shapes.
 */

import type { ApiChallenge, ApiChallengeDetail, ApiMatch } from "@/lib/api";
import type {
  Challenge,
  Domain,
  MatchReason,
  PartnerMatch,
  PriorityFactor,
  Severity,
} from "@/lib/types";

const DOMAINS: Record<string, Domain> = {
  water: "Water & Sanitation",
  sanitation: "Sanitation & Waste",
  health: "Healthcare",
  education: "Education",
  roads: "Roads & Connectivity",
  electricity: "Electricity",
  food: "Food & PDS",
  welfare: "Welfare & Pensions",
  land: "Land & Revenue",
  employment: "Employment & Livelihoods",
  agriculture: "Agriculture & Irrigation",
  safety: "Safety & Environment",
};

const SEVERITIES: Severity[] = ["low", "medium", "high", "critical"];

const PRIORITY_LABELS: Record<string, string> = {
  severity: "Severity",
  affected_population: "Affected population",
  volume: "Complaint volume",
  district_spread: "District spread",
  recurrence: "Recurrence",
};

const PRIORITY_NOTES: Record<string, string> = {
  severity: "mean stated severity of the linked reports",
  affected_population: "log-scaled affected population",
  volume: "log-scaled number of linked reports",
  district_spread: "share of the 24 districts covered",
  recurrence: "share of reports that repeat an earlier text",
};

const PRIORITY_ORDER = [
  "severity",
  "affected_population",
  "volume",
  "district_spread",
  "recurrence",
];

const PRIORITY_DEFAULT_WEIGHTS: Record<string, number> = {
  severity: 0.3,
  affected_population: 0.25,
  volume: 0.2,
  district_spread: 0.15,
  recurrence: 0.1,
};

const MATCH_LABELS: Record<string, string> = {
  tag_overlap: "Capability",
  district_proximity: "Proximity",
  severity: "Severity",
  capacity: "Capacity",
};

const PARTNER_TYPES: Record<string, PartnerMatch["type"]> = {
  university_dept: "University dept",
  research_lab: "Research lab",
  ngo: "NGO",
  industry: "Industry",
  government: "Government",
};

function numericRecord(value: unknown): Record<string, number> {
  if (!value || typeof value !== "object") return {};
  const result: Record<string, number> = {};
  for (const [key, raw] of Object.entries(value)) {
    if (typeof raw === "number" && Number.isFinite(raw)) result[key] = raw;
  }
  return result;
}

export function domainLabel(value: string): Domain {
  return DOMAINS[value] ?? "Other";
}

export function severityLabel(value: string | undefined, score: number): Severity {
  if (value && (SEVERITIES as string[]).includes(value)) return value as Severity;
  if (score >= 0.85) return "critical";
  if (score >= 0.7) return "high";
  if (score >= 0.5) return "medium";
  return "low";
}

export function priorityFactors(
  breakdown: Record<string, unknown>,
): PriorityFactor[] {
  const components = numericRecord(breakdown);
  const weights = { ...PRIORITY_DEFAULT_WEIGHTS };
  for (const [key, value] of Object.entries(numericRecord(breakdown.weights))) {
    weights[key] = value;
  }
  return PRIORITY_ORDER.filter((key) => key in components).map((key) => ({
    label: PRIORITY_LABELS[key],
    weight: weights[key] ?? 0,
    value: components[key],
    note: PRIORITY_NOTES[key],
  }));
}

export function matchReasons(breakdown: Record<string, unknown>): MatchReason[] {
  const components = numericRecord(breakdown.components);
  const weighted = numericRecord(breakdown.weighted);
  return Object.keys(MATCH_LABELS)
    .filter((key) => key in components)
    .map((key) => ({
      label: MATCH_LABELS[key],
      detail:
        weighted[key] !== undefined
          ? `${(components[key] * 100).toFixed(0)}% component · ${weighted[key].toFixed(2)} contribution`
          : `${(components[key] * 100).toFixed(0)}% component`,
    }));
}

export function toPartnerMatch(match: ApiMatch): PartnerMatch {
  return {
    organization: match.organization_name,
    type: PARTNER_TYPES[match.organization_type ?? ""] ?? "Other",
    district: match.organization_districts?.[0] ?? "Jharkhand",
    score: match.score,
    reasons: matchReasons(match.breakdown as Record<string, unknown>),
    status:
      match.status === "expressed_interest"
        ? "interested"
        : (match.status as PartnerMatch["status"]),
  };
}

function monthLabel(value: string): string {
  const [year, month] = value.split("-").map(Number);
  if (!year || !month) return value;
  return new Date(year, month - 1, 1).toLocaleDateString("en-IN", {
    month: "short",
    year: "2-digit",
  });
}

function languageLabel(value: string): string {
  if (value === "hi") return "Hindi";
  if (value === "hinglish") return "Hinglish";
  if (value === "en") return "English";
  return value || "Unknown";
}

/** Full brief, including evidence, districts and trend. */
export function toChallenge(
  detail: ApiChallengeDetail,
  matches: ApiMatch[],
): Challenge {
  return {
    slug: detail.slug,
    title: detail.title,
    summary: detail.summary,
    domain: domainLabel(detail.domain),
    severity: severityLabel(detail.severity, detail.severity_score),
    district: detail.districts[0]?.district ?? "Jharkhand",
    districtCount: detail.district_count || detail.districts.length,
    complaintCount: detail.complaint_count,
    affectedTotal: detail.affected_total,
    priorityScore: Math.round(detail.priority_score),
    priorityFactors: priorityFactors(detail.priority_breakdown),
    firstSeen: detail.first_reported_at ?? "",
    lastSeen: detail.last_reported_at ?? "",
    tags: detail.tags ?? [],
    districts: detail.districts.map((item) => ({
      name: item.district,
      complaints: item.complaints,
    })),
    evidence: detail.evidence.map((item) => ({
      quote: item.quote,
      district: item.district,
      date: item.reported_at,
      language: languageLabel(item.language),
    })),
    timeline: detail.timeline.map((item) => ({
      month: monthLabel(item.month),
      complaints: item.complaints,
    })),
    matches: matches.map(toPartnerMatch),
    status: detail.status === "published" ? "published" : "under_review",
  };
}

/** Card-sized projection of a list row (no evidence or trend yet). */
export function toChallengeCard(challenge: ApiChallenge): Challenge {
  return {
    slug: challenge.slug,
    title: challenge.title,
    summary: challenge.summary,
    domain: domainLabel(challenge.domain),
    severity: severityLabel(challenge.severity, challenge.severity_score),
    district: challenge.district_names?.[0] ?? "Jharkhand",
    districtCount: challenge.district_count ?? challenge.district_names?.length ?? 0,
    complaintCount: challenge.complaint_count,
    affectedTotal: challenge.affected_total,
    priorityScore: Math.round(challenge.priority_score),
    priorityFactors: [],
    firstSeen: challenge.first_reported_at ?? "",
    lastSeen: challenge.last_reported_at ?? "",
    tags: challenge.tags ?? [],
    districts: (challenge.district_names ?? []).map((name) => ({
      name,
      complaints: 0,
    })),
    evidence: [],
    timeline: [],
    matches: [],
    status: challenge.status === "published" ? "published" : "under_review",
  };
}
