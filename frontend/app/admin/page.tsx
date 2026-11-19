"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  GitMerge,
  LayoutDashboard,
  ListChecks,
  Pencil,
  Play,
  RefreshCw,
  ShieldAlert,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { JHARKHAND_DISTRICT_NAMES } from "@/lib/data";
import { RoleGate } from "@/components/role-gate";
import {
  ADMIN_ONLY,
  ROLE_HINTS,
  ROLE_LABELS,
  ROLE_PERMISSIONS,
} from "@/lib/roles";
import {
  ApiError,
  createAdminUser,
  decideMatch,
  fetchAdminChallenges,
  fetchAdminComplaints,
  fetchAdminStats,
  fetchAdminUsers,
  fetchChallengeMatches,
  fetchPartners,
  getAccessToken,
  publishChallenge,
  runRecluster,
  updateAdminUser,
  updateChallenge,
  type ApiAdminStats,
  type ApiAdminUser,
  type ApiChallenge,
  type ApiComplaint,
  type ApiMatch,
  type ApiPartner,
  type ApiRole,
  type ApiUser,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge, PriorityPill } from "@/components/ui";

type Tab = "overview" | "reports" | "challenges" | "users" | "matches";

function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      });
}

type AccountDraft = {
  username: string;
  password: string;
  full_name: string;
  email: string;
  district: string;
  organization_id: string;
  role: ApiRole;
};

export default function AdminPage() {
  return (
    <RoleGate
      allow={ADMIN_ONLY}
      signedOutTitle="Administrator sign-in required"
      signedOutHint="The review console is restricted to administrator accounts. The API rejects every other role with 403."
      deniedTitle="Not available for this account"
    >
      {(user) => <AdminConsole user={user} />}
    </RoleGate>
  );
}

function AdminConsole({ user }: { user: ApiUser }) {
  const [tab, setTab] = useState<Tab>("overview");
  const [stats, setStats] = useState<ApiAdminStats | null>(null);
  const [reports, setReports] = useState<ApiComplaint[]>([]);
  const [challenges, setChallenges] = useState<ApiChallenge[]>([]);
  const [matches, setMatches] = useState<ApiMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [organizations, setOrganizations] = useState<ApiPartner[]>([]);
  const [accounts, setAccounts] = useState<ApiAdminUser[]>([]);
  const [staffBusy, setStaffBusy] = useState(false);
  const [staffForm, setStaffForm] = useState<AccountDraft>({
    username: "",
    password: "",
    full_name: "",
    email: "",
    district: "Ranchi",
    organization_id: "",
    role: "partner",
  });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [titleDraft, setTitleDraft] = useState("");

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const [statsPayload, challengeList, reportList, orgList, accountList] =
        await Promise.all([
          fetchAdminStats(token),
          fetchAdminChallenges(token),
          fetchAdminComplaints(token),
          fetchPartners(),
          fetchAdminUsers(token),
        ]);
      setStats(statsPayload);
      setChallenges(challengeList);
      setReports(reportList);
      setOrganizations(orgList);
      setAccounts(accountList);
      const perChallenge = await Promise.all(
        challengeList.map((challenge) => fetchChallengeMatches(challenge.slug, token)),
      );
      setMatches(perChallenge.flat().sort((a, b) => b.score - a.score));
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not reach the admin API. Start the API service and try again.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handlePublish(challenge: ApiChallenge) {
    const token = getAccessToken();
    if (!token) return;
    setBusy(`publish-${challenge.id}`);
    setError(null);
    try {
      const updated = await publishChallenge(challenge.id, token);
      setChallenges((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setNotice(`Published “${updated.title}”.`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Publish failed.");
    } finally {
      setBusy(null);
    }
  }

  async function handleDecision(match: ApiMatch, action: "confirm" | "decline") {
    const token = getAccessToken();
    if (!token) return;
    setBusy(`match-${match.id}`);
    setError(null);
    try {
      const updated = await decideMatch(match.id, action, token);
      setMatches((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setNotice(
        `${action === "confirm" ? "Confirmed" : "Declined"} ${updated.organization_name} for “${updated.challenge_title}”.`,
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Decision failed.");
    } finally {
      setBusy(null);
    }
  }

  async function handleRecluster() {
    const token = getAccessToken();
    if (!token) return;
    setBusy("recluster");
    setError(null);
    setNotice(null);
    try {
      const result = await runRecluster(token);
      setNotice(
        `Cluster run finished: ${result.complaints_clustered} reports grouped into ${result.challenges_created} drafts, ${result.matches_created} matches proposed. Drafts must be published before partners see them.`,
      );
      await load();
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "The cluster job failed.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function handleRename(challenge: ApiChallenge) {
    const token = getAccessToken();
    if (!token) return;
    const title = titleDraft.trim();
    if (title.length < 3) {
      setError("A challenge title needs at least 3 characters.");
      return;
    }
    setBusy(`rename-${challenge.id}`);
    setError(null);
    try {
      const updated = await updateChallenge(challenge.id, { title }, token);
      setChallenges((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setEditingId(null);
      setNotice(`Renamed the challenge to “${updated.title}”.`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Rename failed.");
    } finally {
      setBusy(null);
    }
  }

  async function handleCreateStaff(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getAccessToken();
    if (!token) return;
    if (staffForm.role === "partner" && staffForm.organization_id === "") {
      setError("Choose the organisation this staff account belongs to.");
      return;
    }
    if (!staffForm.email.trim()) {
      setError("An email address is required for sign-in.");
      return;
    }
    setStaffBusy(true);
    setError(null);
    try {
      const created = await createAdminUser(
        {
          username: staffForm.username.trim(),
          password: staffForm.password,
          role: staffForm.role,
          full_name: staffForm.full_name.trim(),
          email: staffForm.email.trim(),
          district: staffForm.district || null,
          organization_id:
            staffForm.role === "partner"
              ? Number(staffForm.organization_id)
              : null,
        },
        token,
      );
      setAccounts((current) => [...current, created]);
      setNotice(
        `${ROLE_LABELS[created.role]} account “${created.username}” created. It can sign in now.`,
      );
      setStaffForm({
        username: "",
        password: "",
        full_name: "",
        email: "",
        district: "Ranchi",
        organization_id: "",
        role: "partner",
      });
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not create the account.",
      );
    } finally {
      setStaffBusy(false);
    }
  }

  async function handleAccountUpdate(
    account: ApiAdminUser,
    patch: {
      role?: ApiRole;
      is_active?: boolean;
      email?: string;
      organization_id?: number | null;
    },
  ) {
    const token = getAccessToken();
    if (!token) return;
    setBusy(`account-${account.id}`);
    setError(null);
    try {
      const updated = await updateAdminUser(account.id, patch, token);
      setAccounts((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setNotice(
        `Updated “${updated.username}”: ${ROLE_LABELS[updated.role]}${
          updated.is_active ? "" : " (deactivated)"
        }.`,
      );
      if (account.approval_pending && patch.is_active === true) {
        try {
          setOrganizations(await fetchPartners());
        } catch (caught) {
          setError(
            caught instanceof ApiError
              ? `The account was approved, but the organization list could not be refreshed: ${caught.message}`
              : "The account was approved, but the organization list could not be refreshed.",
          );
        }
      }
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Could not update the account.",
      );
    } finally {
      setBusy(null);
    }
  }

  if (!user) {
    return (
      <div className="shell py-14">
        <div className="max-w-lg rounded-2xl border border-line bg-surface p-8 shadow-card">
          <ShieldAlert className="h-6 w-6 text-amber" aria-hidden />
          <h1 className="mt-3 text-2xl font-extrabold tracking-tight">
            Administrator sign-in required
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-fg-muted">
            The review console is restricted to administrator accounts. The API
            rejects every other role with 403.
          </p>
          <button
            className="mt-6 inline-flex rounded-xl bg-teal px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-deep"
            onClick={() => window.location.href = "/login"}
          >
            Sign in
          </button>
        </div>
      </div>
    );
  }

  if (user.role !== "admin") {
    return (
      <div className="shell py-14">
        <div className="max-w-lg rounded-2xl border border-line bg-surface p-8 shadow-card">
          <ShieldAlert className="h-6 w-6 text-crimson" aria-hidden />
          <h1 className="mt-3 text-2xl font-extrabold tracking-tight">
            Not available for this account
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-fg-muted">
            You are signed in as <strong>{user.username}</strong> ({user.role}). The
            review console requires the administrator role.
          </p>
          <button
            className="mt-6 inline-flex rounded-xl bg-teal px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-deep"
            onClick={() => window.location.href = user.role === "partner" ? "/staff/dashboard" : "/submit"}
          >
            {user.role === "partner" ? "Open partner portal" : "Report an issue"}
          </button>
        </div>
      </div>
    );
  }

  const pendingMatches = matches.filter((match) => match.status === "suggested");
  const tabs: { id: Tab; label: string; icon: typeof LayoutDashboard }[] = [
    { id: "overview", label: "Overview", icon: LayoutDashboard },
    { id: "reports", label: `Client issues (${reports.length})`, icon: ListChecks },
    { id: "challenges", label: `Challenges (${challenges.length})`, icon: CheckCircle2 },
    { id: "users", label: `Accounts (${accounts.length})`, icon: Users },
    { id: "matches", label: `Matches (${pendingMatches.length})`, icon: GitMerge },
  ];

  return (
    <div className="shell py-10 sm:py-14">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Administration</p>
          <h1 className="h1 mt-2 text-3xl sm:text-4xl">Review console</h1>
          <p className="mt-2 text-sm text-fg-muted">
            Cluster naming, publishing and partner matches all pass through a human.
          </p>
        </div>
        <Badge tone="teal">
          <ShieldAlert className="h-3.5 w-3.5" aria-hidden />
          Signed in as {user.username}
        </Badge>
      </div>

      <div className="mt-8 flex gap-1 overflow-x-auto border-b border-line pb-px no-scrollbar">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            aria-current={tab === item.id ? "page" : undefined}
            className={cn(
              "-mb-px inline-flex shrink-0 items-center gap-2 border-b-2 px-3.5 py-2.5 text-sm font-semibold transition",
              tab === item.id
                ? "border-teal text-fg"
                : "border-transparent text-fg-muted hover:text-fg",
            )}
          >
            <item.icon className="h-4 w-4" aria-hidden />
            {item.label}
          </button>
        ))}
      </div>

      {error ? (
        <p
          role="alert"
          className="mt-5 flex items-start gap-2 rounded-xl bg-crimson/5 px-3 py-2 text-sm text-crimson"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {error}
        </p>
      ) : null}
      {notice ? (
        <p
          role="status"
          className="mt-5 rounded-xl border border-teal/25 bg-teal/5 px-3 py-2 text-sm text-fg-strong"
        >
          {notice}
        </p>
      ) : null}

      {loading ? (
        <div className="mt-6 h-48 animate-pulse rounded-2xl border border-line bg-surface-2" aria-hidden />
      ) : null}

      {!loading && tab === "overview" ? (
        <div className="mt-6 space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                label: "Complaints",
                value: stats?.complaints ?? 0,
                note: `${stats?.pending ?? 0} pending · ${stats?.merged ?? 0} merged`,
              },
              {
                label: "Published challenges",
                value: stats?.published ?? 0,
                note: `${stats?.challenges ?? 0} total including drafts`,
              },
              {
                label: "Partner matches",
                value: stats?.matches ?? 0,
                note: `${pendingMatches.length} unconfirmed`,
              },
              {
                label: "Citizen feedback",
                value: stats?.feedback ?? 0,
                note: `${stats?.users ?? 0} registered users`,
              },
            ].map((stat) => (
              <div key={stat.label} className="card p-5">
                <p className="text-3xl font-extrabold tracking-tight">{stat.value}</p>
                <p className="mt-1 text-sm font-medium text-fg-strong">{stat.label}</p>
                <p className="mt-0.5 text-xs text-fg-subtle">{stat.note}</p>
              </div>
            ))}
          </div>

          <div className="card flex flex-wrap items-center justify-between gap-4 p-6">
            <div className="max-w-xl">
              <h2 className="text-sm font-bold">Automatic clustering</h2>
              <p className="mt-1 text-xs leading-relaxed text-fg-muted">
                Every new client report is re-clustered in the background as soon as
                it is submitted, so drafts, priority scores and partner matches stay
                current without a manual click. Use this button only to force a run —
                for example after merging duplicates. Published challenges are never
                touched; previous drafts are replaced.
              </p>
            </div>
            <button
              type="button"
              disabled={busy === "recluster"}
              onClick={() => void handleRecluster()}
              className="inline-flex items-center gap-2 rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busy === "recluster" ? (
                <RefreshCw className="h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <Play className="h-4 w-4" aria-hidden />
              )}
              {busy === "recluster" ? "Clustering…" : "Re-run clustering"}
            </button>
          </div>

          <div className="card p-6">
            <h2 className="flex items-center gap-2 text-sm font-bold">
              <UserPlus className="h-4 w-4 text-teal" aria-hidden />
              Create a partner account
            </h2>
            <p className="mt-1 text-xs leading-relaxed text-fg-muted">
              Partner accounts cannot self-register. Issuing one links the login to a
              directory organisation, whose capability tags and districts drive the
              match score it sees.
            </p>
            <form
              className="mt-4 grid gap-3 sm:grid-cols-2"
              onSubmit={handleCreateStaff}
            >
              <label className="text-xs font-semibold text-fg-soft">
                Username
                <input
                  required
                  minLength={3}
                  maxLength={32}
                  value={staffForm.username}
                  onChange={(event) =>
                    setStaffForm((current) => ({
                      ...current,
                      username: event.target.value,
                    }))
                  }
                  className="mt-1 block w-full rounded-lg border border-line-strong bg-surface px-2.5 py-1.5 text-xs text-fg outline-none focus:border-teal"
                />
              </label>
              <label className="text-xs font-semibold text-fg-soft">
                Password
                <input
                  required
                  minLength={12}
                  type="password"
                  autoComplete="new-password"
                  value={staffForm.password}
                  onChange={(event) =>
                    setStaffForm((current) => ({
                      ...current,
                      password: event.target.value,
                    }))
                  }
                  className="mt-1 block w-full rounded-lg border border-line-strong bg-surface px-2.5 py-1.5 text-xs text-fg outline-none focus:border-teal"
                />
              </label>
              <label className="text-xs font-semibold text-fg-soft">
                Email (required for sign-in)
                <input
                  type="email"
                  required
                  maxLength={254}
                  value={staffForm.email}
                  onChange={(event) =>
                    setStaffForm((current) => ({
                      ...current,
                      email: event.target.value,
                    }))
                  }
                  placeholder="name@example.com"
                  className="mt-1 block w-full rounded-lg border border-line-strong bg-surface px-2.5 py-1.5 text-xs text-fg outline-none focus:border-teal"
                />
              </label>
              <label className="text-xs font-semibold text-fg-soft">
                Full name
                <input
                  value={staffForm.full_name}
                  onChange={(event) =>
                    setStaffForm((current) => ({
                      ...current,
                      full_name: event.target.value,
                    }))
                  }
                  className="mt-1 block w-full rounded-lg border border-line-strong bg-surface px-2.5 py-1.5 text-xs text-fg outline-none focus:border-teal"
                />
              </label>
              <label className="text-xs font-semibold text-fg-soft">
                Organisation
                <select
                  required
                  value={staffForm.organization_id}
                  onChange={(event) =>
                    setStaffForm((current) => ({
                      ...current,
                      organization_id: event.target.value,
                    }))
                  }
                  className="mt-1 block w-full rounded-lg border border-line-strong bg-surface px-2.5 py-1.5 text-xs text-fg outline-none focus:border-teal"
                >
                  <option value="" disabled>
                    {organizations.length ? "Choose an organisation" : "No organisations"}
                  </option>
                  {organizations.map((organization) => (
                    <option key={organization.id} value={organization.id}>
                      {organization.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs font-semibold text-fg-soft">
                District
                <select
                  value={staffForm.district}
                  onChange={(event) =>
                    setStaffForm((current) => ({
                      ...current,
                      district: event.target.value,
                    }))
                  }
                  className="mt-1 block w-full rounded-lg border border-line-strong bg-surface px-2.5 py-1.5 text-xs text-fg outline-none focus:border-teal"
                >
                  {JHARKHAND_DISTRICT_NAMES.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="submit"
                disabled={staffBusy || organizations.length === 0}
                className="mt-1 inline-flex items-center justify-center gap-1.5 self-end rounded-lg bg-teal px-3 py-2 text-xs font-semibold text-white hover:bg-teal-deep disabled:cursor-not-allowed disabled:opacity-60"
              >
                <UserPlus className="h-3.5 w-3.5" aria-hidden />
                {staffBusy ? "Creating…" : "Create partner account"}
              </button>
            </form>
          </div>

          <p className="text-[11px] leading-relaxed text-fg-subtle">
            Every number on this page is read from the API database. The demo
            database is seeded with synthetic complaints, so these are not real
            Jharkhand grievance statistics.
          </p>
        </div>
      ) : null}

      {!loading && tab === "reports" ? (
        <div className="mt-6">
          <p className="text-sm text-fg-muted">
            All client reports, their clustering state, and the latest staff
            progress update. Staff responses are saved with their date and time.
          </p>
          {reports.length === 0 ? (
            <div className="mt-6 card p-10 text-center">
              <CheckCircle2 className="mx-auto h-8 w-8 text-teal" aria-hidden />
              <p className="mt-2 text-sm font-semibold">No client reports</p>
              <p className="text-xs text-fg-subtle">
                New submissions will appear here with their progress history.
              </p>
            </div>
          ) : (
            <div className="mt-4 overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[900px] text-left text-sm">
                  <caption className="sr-only">Client reports and latest staff progress</caption>
                  <thead className="bg-surface-2 text-[11px] uppercase tracking-wider text-fg-subtle">
                    <tr>
                      <th scope="col" className="px-4 py-3 font-semibold">Report</th>
                      <th scope="col" className="px-4 py-3 font-semibold">District</th>
                      <th scope="col" className="hidden px-4 py-3 font-semibold sm:table-cell">Severity</th>
                      <th scope="col" className="hidden px-4 py-3 font-semibold md:table-cell">Text</th>
                      <th scope="col" className="px-4 py-3 font-semibold">Progress / latest staff update</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {reports.map((report) => (
                      <tr key={report.report_id} className="hover:bg-surface-2/60">
                        <td className="px-4 py-3">
                          <p className="font-mono text-xs font-semibold text-fg">
                            {report.report_id}
                          </p>
                          <p className="mt-1 text-[11px] text-fg-subtle">
                            Submitted{" "}
                            <time dateTime={report.reported_at}>
                              {formatDateTime(report.reported_at)}
                            </time>
                          </p>
                        </td>
                        <td className="px-4 py-3 text-xs text-fg-soft">{report.district}</td>
                        <td className="hidden px-4 py-3 text-xs capitalize text-fg-soft sm:table-cell">
                          {report.severity}
                        </td>
                        <td className="hidden max-w-md px-4 py-3 text-xs text-fg-soft md:table-cell">
                          <span className="line-clamp-2">{report.report_text}</span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge
                              tone={
                                report.staff_response_status === "resolved"
                                  ? "teal"
                                  : report.staff_response_status
                                    ? "amber"
                                    : "neutral"
                              }
                            >
                              {report.staff_response_status
                                ? report.staff_response_status.replace(/_/g, " ")
                                : "Awaiting staff update"}
                            </Badge>
                            <Badge tone={report.status === "pending" ? "amber" : "neutral"}>
                              Report: {report.status}
                            </Badge>
                          </div>
                          {report.staff_response_text ? (
                            <p className="mt-2 max-w-md text-xs leading-relaxed text-fg-soft">
                              {report.staff_response_text}
                            </p>
                          ) : (
                            <p className="mt-2 text-xs text-fg-subtle">
                              No staff progress update has been recorded.
                            </p>
                          )}
                          {report.staff_responded_at ? (
                            <p className="mt-1 text-[11px] text-fg-subtle">
                              Updated{" "}
                              <time dateTime={report.staff_responded_at}>
                                {formatDateTime(report.staff_responded_at)}
                              </time>
                            </p>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      ) : null}

      {!loading && tab === "challenges" ? (
        <div className="mt-6 overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
          {challenges.length === 0 ? (
            <div className="p-10 text-center">
              <p className="text-sm font-semibold">No challenges yet</p>
              <p className="mt-1 text-xs text-fg-subtle">
                New reports are clustered automatically; drafts appear here once a run has grouped two or more active reports. The Overview tab can force a re-run.
              </p>
            </div>
          ) : (
            <table className="w-full text-left text-sm">
              <caption className="sr-only">All challenges, including drafts</caption>
              <thead className="bg-surface-2 text-[11px] uppercase tracking-wider text-fg-subtle">
                <tr>
                  <th scope="col" className="px-5 py-3 font-semibold">Challenge</th>
                  <th scope="col" className="hidden px-5 py-3 font-semibold sm:table-cell">Domain</th>
                  <th scope="col" className="hidden px-5 py-3 font-semibold md:table-cell">Reports</th>
                  <th scope="col" className="px-5 py-3 font-semibold">Priority</th>
                  <th scope="col" className="px-5 py-3 text-right font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {challenges.map((challenge) => (
                  <tr key={challenge.id} className="hover:bg-surface-2/60">
                    <td className="px-5 py-3">
                      {editingId === challenge.id ? (
                        <form
                          className="flex flex-wrap items-center gap-2"
                          onSubmit={(event) => {
                            event.preventDefault();
                            void handleRename(challenge);
                          }}
                        >
                          <input
                            value={titleDraft}
                            onChange={(event) => setTitleDraft(event.target.value)}
                            aria-label="Challenge title"
                            minLength={3}
                            maxLength={160}
                            className="w-full max-w-xs rounded-lg border border-line-strong bg-surface px-2.5 py-1.5 text-xs outline-none focus:border-teal"
                          />
                          <button
                            type="submit"
                            disabled={busy === `rename-${challenge.id}`}
                            className="rounded-lg bg-teal px-2.5 py-1.5 text-[11px] font-semibold text-white disabled:opacity-60"
                          >
                            Save
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingId(null)}
                            className="rounded-lg border border-line-strong px-2.5 py-1.5 text-[11px] font-semibold text-fg-soft"
                          >
                            Cancel
                          </button>
                        </form>
                      ) : (
                        <>
                          <p className="max-w-xs font-medium text-fg">
                            {challenge.title}
                          </p>
                          <div className="mt-0.5 flex items-center gap-2">
                            <p className="font-mono text-[10px] text-fg-subtle">
                              {challenge.slug}
                            </p>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingId(challenge.id);
                                setTitleDraft(challenge.title);
                              }}
                              className="inline-flex items-center gap-1 text-[10px] font-semibold text-teal hover:underline"
                            >
                              <Pencil className="h-3 w-3" aria-hidden />
                              Rename
                            </button>
                          </div>
                        </>
                      )}
                    </td>
                    <td className="hidden px-5 py-3 text-xs text-fg-soft sm:table-cell">
                      {challenge.domain}
                    </td>
                    <td className="hidden px-5 py-3 text-xs text-fg-soft md:table-cell">
                      {challenge.complaint_count}
                    </td>
                    <td className="px-5 py-3">
                      <PriorityPill score={Math.round(challenge.priority_score)} />
                    </td>
                    <td className="px-5 py-3 text-right">
                      {challenge.status === "published" ? (
                        <Badge tone="teal">Published</Badge>
                      ) : (
                        <button
                          type="button"
                          disabled={busy === `publish-${challenge.id}`}
                          onClick={() => void handlePublish(challenge)}
                          className="rounded-lg bg-amber/10 px-2.5 py-1 text-[11px] font-semibold text-amber transition hover:bg-amber/15 disabled:opacity-60"
                        >
                          {busy === `publish-${challenge.id}` ? "Publishing…" : "Publish"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : null}

      {!loading && tab === "users" ? (
        <div className="mt-6 space-y-3">
          <div className="card p-5">
            <h2 className="text-sm font-bold">Accounts</h2>
            <p className="mt-1 text-xs leading-relaxed text-fg-muted">
              Review partner account requests here. Email is required for sign-in,
              and disabled accounts cannot sign in even with a valid password.
            </p>
          </div>
          <section aria-labelledby="role-permissions-heading">
            <h2 id="role-permissions-heading" className="mb-2 text-sm font-bold">
              Role permissions
            </h2>
            <div className="grid gap-3 md:grid-cols-3">
              {(["admin", "partner", "citizen"] as const).map((role) => (
                <div key={role} className="card p-4">
                  <h3 className="text-xs font-bold">{ROLE_LABELS[role]}</h3>
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-relaxed text-fg-muted">
                    {ROLE_PERMISSIONS[role].map((permission) => (
                      <li key={permission}>{permission}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-fg-subtle">
              Citizens can only access their own reports. Staff only see matches
              for their linked organisation. Published challenge briefs are public.
            </p>
          </section>
          {accounts.length === 0 ? (
            <div className="card p-10 text-center">
              <Users className="mx-auto h-8 w-8 text-teal" aria-hidden />
              <p className="mt-2 text-sm font-semibold">No accounts yet</p>
              <p className="text-xs text-fg-subtle">
                Create a partner account from the Overview tab.
              </p>
            </div>
          ) : (
            accounts.map((account) => (
              <AccountRow
                key={account.id}
                account={account}
                organizations={organizations}
                busy={busy === `account-${account.id}`}
                isSelf={account.id === user.id}
                onUpdate={(patch) => handleAccountUpdate(account, patch)}
              />
            ))
          )}
        </div>
      ) : null}

      {!loading && tab === "matches" ? (
        <div className="mt-6 space-y-3">
          {matches.length === 0 ? (
            <div className="card p-10 text-center">
              <GitMerge className="mx-auto h-8 w-8 text-teal" aria-hidden />
              <p className="mt-2 text-sm font-semibold">No matches proposed</p>
              <p className="text-xs text-fg-subtle">
                Partners are proposed automatically with each cluster. Force a re-run from the Overview tab if a published challenge has no matches.
              </p>
            </div>
          ) : (
            matches.map((match) => (
              <div key={match.id} className="card p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="max-w-2xl">
                    <p className="text-sm font-bold text-fg">
                      {match.organization_name} → {match.challenge_title}
                    </p>
                    <p className="mt-1 text-xs text-fg-muted">
                      Match #{match.id} · score {match.score.toFixed(2)}
                    </p>
                    {Object.keys(match.breakdown?.components ?? {}).length > 0 ? (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {Object.entries(match.breakdown.components ?? {}).map(
                          ([key, value]) => (
                            <span
                              key={key}
                              className="rounded-full bg-surface-2 px-2 py-0.5 text-[10px] text-fg-soft"
                            >
                              {key.replace(/_/g, " ")}: {value.toFixed(2)}
                            </span>
                          ),
                        )}
                      </div>
                    ) : null}
                  </div>
                  <Badge
                    tone={
                      match.status === "confirmed"
                        ? "teal"
                        : match.status === "declined"
                          ? "neutral"
                          : "amber"
                    }
                  >
                    {match.status.replace(/_/g, " ")}
                  </Badge>
                </div>

                {match.status === "suggested" ? (
                  <div className="mt-4 flex gap-2 border-t border-line pt-3">
                    <button
                      type="button"
                      disabled={busy === `match-${match.id}`}
                      onClick={() => void handleDecision(match, "confirm")}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-teal px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-deep disabled:opacity-60"
                    >
                      <Check className="h-3.5 w-3.5" aria-hidden />
                      Confirm match
                    </button>
                    <button
                      type="button"
                      disabled={busy === `match-${match.id}`}
                      onClick={() => void handleDecision(match, "decline")}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong px-3 py-1.5 text-xs font-semibold text-fg-soft hover:bg-fg/5 disabled:opacity-60"
                    >
                      <X className="h-3.5 w-3.5" aria-hidden />
                      Decline
                    </button>
                  </div>
                ) : null}
              </div>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}

function AccountRow({
  account,
  organizations,
  busy,
  isSelf,
  onUpdate,
}: {
  account: ApiAdminUser;
  organizations: ApiPartner[];
  busy: boolean;
  isSelf: boolean;
  onUpdate: (patch: {
    role?: ApiRole;
    is_active?: boolean;
    email?: string;
    organization_id?: number | null;
  }) => Promise<void>;
}) {
  const [email, setEmail] = useState(account.email ?? "");

  // A saved update comes back from the API; keep the field in step with it.
  useEffect(() => {
    setEmail(account.email ?? "");
  }, [account.email]);

  const emailChanged = email.trim() !== (account.email ?? "");

  return (
    <div className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-bold">
            {account.full_name || account.username}
          </p>
          <p className="font-mono text-[11px] text-fg-subtle">{account.username}</p>
          {account.organization_name ? (
            <p className="mt-1 text-xs text-fg-muted">
              {account.organization_name}
              {account.job_title ? ` · ${account.job_title}` : ""}
            </p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
        {isSelf ? <Badge tone="teal">You</Badge> : null}
        <Badge
          tone={
            account.is_active
              ? "teal"
              : account.approval_pending
                ? "amber"
                : "crimson"
          }
        >
          {account.is_active
            ? "Active"
            : account.approval_pending
              ? "Pending approval"
              : "Disabled"}
        </Badge>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <label className="text-xs font-semibold text-fg-soft">
          Email (required for sign-in)
          <div className="mt-1 flex gap-1.5">
            <input
              type="email"
              required
              maxLength={254}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="name@example.com"
              className="block w-full min-w-0 rounded-lg border border-line-strong bg-surface px-2.5 py-1.5 text-xs text-fg outline-none focus:border-teal"
            />
            <button
              type="button"
              disabled={!emailChanged || !email.trim() || busy}
              onClick={() => void onUpdate({ email: email.trim() })}
              className="shrink-0 rounded-lg bg-teal px-2.5 py-1.5 text-[11px] font-semibold text-white hover:bg-teal-deep disabled:cursor-not-allowed disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </label>

        <label className="text-xs font-semibold text-fg-soft">
          Role
          <select
            value={account.role}
            disabled={isSelf || busy}
            onChange={(event) =>
              void onUpdate({ role: event.target.value as ApiRole })
            }
            className="mt-1 block w-full rounded-lg border border-line-strong bg-surface px-2.5 py-1.5 text-xs text-fg outline-none focus:border-teal disabled:opacity-50"
          >
            {(["citizen", "partner", "admin"] as const).map((role) => (
              <option key={role} value={role}>
                {ROLE_LABELS[role]}
              </option>
            ))}
          </select>
        </label>

        <label className="text-xs font-semibold text-fg-soft">
          Organisation
          <select
            value={account.organization_id ?? ""}
            disabled={busy}
            onChange={(event) =>
              void onUpdate({
                organization_id:
                  event.target.value === "" ? null : Number(event.target.value),
              })
            }
            className="mt-1 block w-full rounded-lg border border-line-strong bg-surface px-2.5 py-1.5 text-xs text-fg outline-none focus:border-teal disabled:opacity-50"
          >
            <option value="">Not linked</option>
            {organizations.map((organization) => (
              <option key={organization.id} value={organization.id}>
                {organization.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
        <div>
          <p className="text-[11px] text-fg-subtle">
            {ROLE_HINTS[account.role]}
          </p>
          <p className="mt-1 text-[11px] leading-relaxed text-fg-muted">
            Permissions: {ROLE_PERMISSIONS[account.role].join(" · ")}
          </p>
        </div>
        <button
          type="button"
          disabled={isSelf || busy}
          onClick={() => void onUpdate({ is_active: !account.is_active })}
          className={cn(
            "rounded-lg border px-2.5 py-1 text-[11px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-50",
            account.is_active
              ? "border-crimson/25 text-crimson hover:bg-crimson/5"
              : "border-teal/25 text-teal hover:bg-teal/5",
          )}
        >
          {account.is_active
            ? "Deactivate"
            : account.approval_pending
              ? "Approve"
              : "Reactivate"}
        </button>
      </div>
    </div>
  );
}
