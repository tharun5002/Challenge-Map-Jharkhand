/**
 * Typed client for the Phase 5 FastAPI service.
 *
 * The base URL is public (`NEXT_PUBLIC_API_BASE`) because the browser calls the
 * same endpoints as the server components. Nothing here is trusted for
 * authorisation — every role check happens in api/deps.py.
 */

export const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const DEFAULT_TIMEOUT_MS = 4000;

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export type ApiRole = "citizen" | "partner" | "admin";

export type ApiUser = {
  id: number;
  username: string;
  full_name: string;
  /** Required for sign-in; the login API does not accept usernames. */
  email?: string | null;
  role: ApiRole;
  district: string | null;
  organization_id: number | null;
};

export type ApiTokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
};

export type ApiLoginResponse = ApiTokenPair & { user: ApiUser };

export type ApiChallenge = {
  id: number;
  slug: string;
  title: string;
  summary: string;
  domain: string;
  complaint_count: number;
  affected_total: number;
  severity_score: number;
  priority_score: number;
  priority_breakdown: Record<string, unknown>;
  status: "draft" | "under_review" | "published" | "archived";
  published_at: string | null;
  severity?: string;
  district_count?: number;
  district_names?: string[];
  tags?: string[];
  first_reported_at?: string | null;
  last_reported_at?: string | null;
};

export type ApiChallengeDetail = ApiChallenge & {
  severity: string;
  district_count: number;
  district_names: string[];
  first_reported_at: string | null;
  last_reported_at: string | null;
  districts: { district: string; complaints: number }[];
  evidence: {
    quote: string;
    district: string;
    reported_at: string;
    language: string;
  }[];
  timeline: { month: string; complaints: number }[];
};

export type MatchBreakdown = {
  components?: Record<string, number>;
  weighted?: Record<string, number>;
  weights?: Record<string, number>;
};

export type ApiMatch = {
  id: number;
  challenge_slug: string;
  challenge_title: string;
  organization_id: number;
  organization_name: string;
  organization_type?: string;
  organization_districts?: string[];
  score: number;
  breakdown: MatchBreakdown;
  status: "suggested" | "confirmed" | "declined" | "expressed_interest";
};

export type ApiDuplicateCandidate = {
  report_id: string;
  similarity: number;
  district: string;
  report_text: string;
};

export type ApiComplaint = {
  report_id: string;
  district: string;
  place: string;
  report_text: string;
  language: string;
  severity: string;
  affected_population: number | null;
  status: string;
  duplicate_of: string | null;
  reported_at: string;
  created_at: string;
  source: string;
  is_synthetic: number;
  staff_response_status:
    | "acknowledged"
    | "in_progress"
    | "resolved"
    | "unable_to_resolve"
    | null;
  staff_response_text: string | null;
  staff_responded_at: string | null;
};

export type ApiStaffResponse = {
  response_id: number;
  report_id: string;
  status: "acknowledged" | "in_progress" | "resolved" | "unable_to_resolve";
  response_text: string;
  created_at: string;
};

export type ApiComplaintSubmit = ApiComplaint & {
  duplicate_candidates: ApiDuplicateCandidate[];
};

export type ApiPartner = {
  id: number;
  name: string;
  org_type: string;
  capability_tags: string[];
  districts: string[];
  capacity: number;
  contact_email: string;
};

export type ApiAdminStats = {
  users: number;
  complaints: number;
  pending: number;
  clustered: number;
  merged: number;
  challenges: number;
  published: number;
  matches: number;
  feedback: number;
};

export type ApiReclusterResult = {
  challenges_created: number;
  complaints_clustered: number;
  matches_created: number;
};

export type ApiFeedback = {
  feedback_id: number;
  report_id: string;
  status: "Not solved" | "Partially solved" | "Solved";
  feedback_text: string;
  submitted_at: string;
};

export type ApiAdminUser = ApiUser & {
  organization_name: string | null;
  job_title: string;
  approval_pending: boolean;
  is_active: boolean;
  created_at: string;
};

export type ComplaintInput = {
  district: string;
  place?: string;
  report_text: string;
  language?: string;
  severity?: "unknown" | "low" | "medium" | "high" | "critical";
  affected_population?: number | null;
};

/* ---------------------------------------------------------------- session -- */

const ACCESS_KEY = "challengemap.access_token";
const REFRESH_KEY = "challengemap.refresh_token";
const USER_KEY = "challengemap.user";

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload: unknown = await response.json();
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) => (item as { msg?: string }).msg ?? "invalid value")
        .join("; ");
    }
  } catch {
    // Fall through to a generic message: the body was not JSON.
  }
  return `Request failed with status ${response.status}.`;
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  token?: string | null;
  timeoutMs?: number;
  /** Internal: prevents an endless 401 → refresh → 401 loop. */
  skipRefresh?: boolean;
};

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  );
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.token) headers.Authorization = `Bearer ${options.token}`;

  try {
    const response = await fetch(`${API_BASE}/api/v1${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) {
      // A short-lived access token can expire mid-session. Rotate the refresh
      // token once and replay the request rather than signing the user out.
      if (response.status === 401 && options.token && !options.skipRefresh) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
          return apiRequest<T>(path, {
            ...options,
            token: refreshed,
            skipRefresh: true,
          });
        }
      }
      throw new ApiError(response.status, await errorMessage(response));
    }
    return (await response.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  refreshInFlight = (async () => {
    try {
      const pair = await apiRequest<ApiTokenPair>("/auth/refresh", {
        method: "POST",
        body: { refresh_token: refreshToken },
        skipRefresh: true,
      });
      window.localStorage.setItem(ACCESS_KEY, pair.access_token);
      window.localStorage.setItem(REFRESH_KEY, pair.refresh_token);
      return pair.access_token;
    } catch {
      clearSession();
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY);
}

export function getSessionUser(): ApiUser | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ApiUser;
  } catch {
    return null;
  }
}

export function saveSession(session: ApiLoginResponse): void {
  window.localStorage.setItem(ACCESS_KEY, session.access_token);
  window.localStorage.setItem(REFRESH_KEY, session.refresh_token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(session.user));
}

export function clearSession(): void {
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
  window.localStorage.removeItem(USER_KEY);
}

/* ------------------------------------------------------------- endpoints -- */

export async function login(
  email: string,
  password: string,
  role: ApiRole,
): Promise<ApiLoginResponse> {
  return apiRequest<ApiLoginResponse>("/auth/login", {
    method: "POST",
    body: { email, password, role },
  });
}

export async function registerAccount(input: {
  username: string;
  email: string;
  password: string;
  full_name: string;
  district: string | null;
}): Promise<ApiUser> {
  return apiRequest<ApiUser>("/auth/register", {
    method: "POST",
    body: {
      username: input.username,
      email: input.email,
      password: input.password,
      password_confirmation: input.password,
      full_name: input.full_name,
      district: input.district,
    },
  });
}

export async function registerPartnerAccount(input: {
  username: string;
  email: string;
  password: string;
  full_name: string;
  district: string | null;
  organization_name: string;
  job_title: string;
}): Promise<{ message: string }> {
  return apiRequest<{ message: string }>("/auth/register/partner", {
    method: "POST",
    body: {
      ...input,
      password_confirmation: input.password,
    },
  });
}

export async function submitComplaint(
  input: ComplaintInput,
  token: string,
): Promise<ApiComplaintSubmit> {
  return apiRequest<ApiComplaintSubmit>("/complaints", {
    method: "POST",
    token,
    body: {
      district: input.district,
      place: input.place ?? "",
      report_text: input.report_text,
      language: input.language ?? "unknown",
      severity: input.severity ?? "unknown",
      affected_population: input.affected_population ?? null,
    },
  });
}

export async function mergeComplaint(
  reportId: string,
  keepReportId: string,
  token: string,
): Promise<ApiComplaint> {
  return apiRequest<ApiComplaint>(
    `/complaints/${encodeURIComponent(reportId)}/merge`,
    {
      method: "POST",
      token,
      body: { keep_report_id: keepReportId },
    },
  );
}

export async function listMyComplaints(token: string): Promise<ApiComplaint[]> {
  return apiRequest<ApiComplaint[]>("/complaints", { token });
}

/**
 * Public reads used by server components. They resolve to `null` when the API
 * is unreachable, which lets the UI fall back to the bundled demo dataset
 * instead of showing an error page.
 */
export async function fetchPublishedChallenges(): Promise<ApiChallenge[] | null> {
  try {
    return await apiRequest<ApiChallenge[]>("/challenges?limit=100");
  } catch {
    return null;
  }
}

export async function fetchChallenge(slug: string): Promise<ApiChallenge | null> {
  try {
    return await apiRequest<ApiChallenge>(
      `/challenges/${encodeURIComponent(slug)}`,
    );
  } catch {
    return null;
  }
}

export async function fetchChallengeMatches(
  slug: string,
  token?: string | null,
): Promise<ApiMatch[]> {
  try {
    return await apiRequest<ApiMatch[]>(
      `/challenges/${encodeURIComponent(slug)}/matches`,
      { token },
    );
  } catch {
    return [];
  }
}

export async function fetchPartners(): Promise<ApiPartner[]> {
  return apiRequest<ApiPartner[]>("/partners");
}

export async function fetchChallengeDetail(
  slug: string,
  token?: string | null,
): Promise<ApiChallengeDetail | null> {
  try {
    return await apiRequest<ApiChallengeDetail>(
      `/challenges/${encodeURIComponent(slug)}`,
      { token },
    );
  } catch {
    return null;
  }
}

export async function updateChallenge(
  challengeId: number,
  input: { title?: string; summary?: string; domain?: string },
  token: string,
): Promise<ApiChallenge> {
  return apiRequest<ApiChallenge>(`/challenges/${challengeId}`, {
    method: "PATCH",
    token,
    body: input,
  });
}

export async function fetchAdminUsers(token: string): Promise<ApiAdminUser[]> {
  return apiRequest<ApiAdminUser[]>("/admin/users", { token });
}

export async function createAdminUser(
  input: {
    username: string;
    password: string;
    role: ApiRole;
    full_name?: string;
    email: string;
    district?: string | null;
    organization_id?: number | null;
  },
  token: string,
): Promise<ApiAdminUser> {
  return apiRequest<ApiAdminUser>("/admin/users", {
    method: "POST",
    token,
    body: {
      username: input.username,
      password: input.password,
      role: input.role,
      full_name: input.full_name ?? "",
      email: input.email,
      district: input.district ?? null,
      organization_id: input.organization_id ?? null,
    },
  });
}

export async function updateAdminUser(
  userId: number,
  input: {
    role?: ApiRole;
    is_active?: boolean;
    email?: string;
    district?: string | null;
    organization_id?: number | null;
  },
  token: string,
): Promise<ApiAdminUser> {
  return apiRequest<ApiAdminUser>(`/admin/users/${userId}`, {
    method: "PATCH",
    token,
    body: input,
  });
}

/* -------------------------------------------------------------- feedback -- */

export async function submitFeedback(
  reportId: string,
  input: {
    status: "Not solved" | "Partially solved" | "Solved";
    feedback_text: string;
  },
  token: string,
): Promise<ApiFeedback> {
  return apiRequest<ApiFeedback>(
    `/complaints/${encodeURIComponent(reportId)}/feedback`,
    { method: "POST", token, body: input },
  );
}

export async function fetchFeedback(
  reportId: string,
  token: string,
): Promise<ApiFeedback[]> {
  return apiRequest<ApiFeedback[]>(
    `/complaints/${encodeURIComponent(reportId)}/feedback`,
    { token },
  );
}

/* --------------------------------------------------------------- partner -- */

export async function fetchPartnerMatches(token: string): Promise<ApiMatch[]> {
  return apiRequest<ApiMatch[]>("/partners/me/matches", { token });
}

export async function fetchStaffIssues(token: string): Promise<ApiComplaint[]> {
  return apiRequest<ApiComplaint[]>("/staff/issues", { token });
}

export async function respondToStaffIssue(
  reportId: string,
  input: Pick<ApiStaffResponse, "status" | "response_text">,
  token: string,
): Promise<ApiStaffResponse> {
  return apiRequest<ApiStaffResponse>(
    `/staff/issues/${encodeURIComponent(reportId)}/responses`,
    { method: "POST", token, body: input },
  );
}

export async function expressInterest(
  matchId: number,
  token: string,
): Promise<ApiMatch> {
  return apiRequest<ApiMatch>(`/matches/${matchId}/interest`, {
    method: "POST",
    token,
  });
}

/* ----------------------------------------------------------------- admin -- */

export async function fetchAdminStats(token: string): Promise<ApiAdminStats> {
  return apiRequest<ApiAdminStats>("/admin/stats", { token });
}

export async function fetchAdminComplaints(
  token: string,
  status?: string,
): Promise<ApiComplaint[]> {
  const query = status ? `?status=${encodeURIComponent(status)}&limit=100` : "?limit=100";
  return apiRequest<ApiComplaint[]>(`/admin/complaints${query}`, { token });
}

export async function fetchAdminChallenges(
  token: string,
): Promise<ApiChallenge[]> {
  return apiRequest<ApiChallenge[]>("/challenges?status=all&limit=100", {
    token,
  });
}

export async function publishChallenge(
  challengeId: number,
  token: string,
): Promise<ApiChallenge> {
  return apiRequest<ApiChallenge>(`/challenges/${challengeId}/publish`, {
    method: "POST",
    token,
  });
}

export async function decideMatch(
  matchId: number,
  action: "confirm" | "decline",
  token: string,
): Promise<ApiMatch> {
  return apiRequest<ApiMatch>(`/admin/matches/${matchId}`, {
    method: "PATCH",
    token,
    body: { action },
  });
}

export async function runRecluster(
  token: string,
  clusters?: number,
): Promise<ApiReclusterResult> {
  return apiRequest<ApiReclusterResult>("/admin/jobs/recluster", {
    method: "POST",
    token,
    timeoutMs: 60_000,
    body: clusters ? { clusters } : {},
  });
}
