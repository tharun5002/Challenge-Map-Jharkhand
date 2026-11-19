export type Domain =
  | "Water & Sanitation"
  | "Sanitation & Waste"
  | "Healthcare"
  | "Education"
  | "Roads & Connectivity"
  | "Electricity"
  | "Food & PDS"
  | "Welfare & Pensions"
  | "Land & Revenue"
  | "Employment & Livelihoods"
  | "Agriculture & Irrigation"
  | "Safety & Environment"
  | "Other";

export type Severity = "critical" | "high" | "medium" | "low";

export type PriorityFactor = {
  label: string;
  weight: number;
  value: number;
  note: string;
};

export type MatchReason = {
  label: string;
  detail: string;
};

export type PartnerMatch = {
  organization: string;
  type: "University dept" | "Research lab" | "NGO" | "Industry" | "Government" | "Other";
  district: string;
  score: number;
  reasons: MatchReason[];
  status: "suggested" | "confirmed" | "interested" | "declined";
};

export type Challenge = {
  slug: string;
  title: string;
  summary: string;
  domain: Domain;
  severity: Severity;
  district: string;
  districtCount: number;
  complaintCount: number;
  affectedTotal: number;
  priorityScore: number;
  priorityFactors: PriorityFactor[];
  firstSeen: string;
  lastSeen: string;
  tags: string[];
  districts: { name: string; complaints: number }[];
  evidence: { quote: string; district: string; date: string; language: string }[];
  timeline: { month: string; complaints: number }[];
  matches: PartnerMatch[];
  status: "published" | "under_review";
};

export type DistrictStat = {
  name: string;
  complaints: number;
  critical: number;
};

export type Partner = {
  name: string;
  type: PartnerMatch["type"];
  district: string;
  focus: string[];
  activeChallenges: number;
  blurb: string;
};

export type SubmittedComplaint = {
  id: string;
  text: string;
  district: string;
  domain: Domain;
  date: string;
};
