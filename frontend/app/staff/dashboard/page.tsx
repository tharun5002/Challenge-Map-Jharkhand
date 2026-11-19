"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, Building2, CheckCircle2, Send } from "lucide-react";
import { RoleGate } from "@/components/role-gate";
import { STAFF_PORTAL_ROLES } from "@/lib/roles";
import {
  ApiError,
  fetchStaffIssues,
  getAccessToken,
  respondToStaffIssue,
  type ApiComplaint,
  type ApiStaffResponse,
} from "@/lib/api";
import { Badge } from "@/components/ui";

type StaffResponseStatus = ApiStaffResponse["status"];

const RESPONSE_STATUSES: { value: StaffResponseStatus; label: string }[] = [
  { value: "acknowledged", label: "Acknowledged" },
  { value: "in_progress", label: "In progress" },
  { value: "resolved", label: "Resolved" },
  { value: "unable_to_resolve", label: "Unable to resolve" },
];

const RESPONSE_LABELS = Object.fromEntries(
  RESPONSE_STATUSES.map(({ value, label }) => [value, label]),
) as Record<StaffResponseStatus, string>;

export default function StaffDashboardPage() {
  return (
    <RoleGate
      allow={STAFF_PORTAL_ROLES}
      signedOutTitle="Staff sign-in required"
      signedOutHint="Sign in with an approved staff account to review client reports."
      deniedTitle="Staff access required"
    >
      {(user) => (
        <StaffIssueQueue
          name={user.full_name || user.username}
          scope="your organisation's districts"
        />
      )}
    </RoleGate>
  );
}

function StaffIssueQueue({ name, scope }: { name: string; scope: string }) {
  const [issues, setIssues] = useState<ApiComplaint[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setError(null);
    try {
      setIssues(await fetchStaffIssues(token));
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not load client reports. Check the API connection and try again.",
      );
      setIssues([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleResponse(
    reportId: string,
    status: StaffResponseStatus,
    responseText: string,
  ): Promise<boolean> {
    const token = getAccessToken();
    if (!token) return false;
    setBusyId(reportId);
    setError(null);
    try {
      const response = await respondToStaffIssue(
        reportId,
        { status, response_text: responseText },
        token,
      );
      setIssues((current) =>
        current?.map((issue) =>
          issue.report_id === reportId
            ? {
                ...issue,
                staff_response_status: response.status,
                staff_response_text: response.response_text,
                staff_responded_at: response.created_at,
              }
            : issue,
        ) ?? current,
      );
      setNotice(`Your update for report ${reportId} was sent to the client.`);
      return true;
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not send your update. Try again.",
      );
      return false;
    } finally {
      setBusyId(null);
    }
  }

  const waiting = issues?.filter((issue) => !issue.staff_response_status).length ?? 0;
  const active = issues?.filter(
    (issue) => issue.staff_response_status === "in_progress",
  ).length ?? 0;

  return (
    <div className="shell py-10 sm:py-14">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Staff portal · Client issues</p>
          <h1 className="h1 mt-2 text-3xl sm:text-4xl">Respond to reports</h1>
          <p className="mt-2 inline-flex items-center gap-1.5 text-sm text-fg-muted">
            <Building2 className="h-4 w-4" aria-hidden />
            {name} · reports from {scope}
          </p>
        </div>
        <Link
          href="/partners/dashboard"
          className="rounded-xl border border-line-strong px-4 py-2.5 text-sm font-semibold text-fg-strong transition hover:bg-fg/5"
        >
          View matched challenges
        </Link>
      </div>

      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        {[
          { label: "Client reports", value: issues?.length ?? "—" },
          { label: "Awaiting response", value: issues === null ? "—" : waiting },
          { label: "In progress", value: issues === null ? "—" : active },
        ].map((stat) => (
          <div key={stat.label} className="card p-5">
            <p className="text-3xl font-extrabold tracking-tight">{stat.value}</p>
            <p className="mt-1 text-sm text-fg-muted">{stat.label}</p>
          </div>
        ))}
      </div>

      {error ? (
        <p
          role="alert"
          className="mt-6 flex items-start gap-2 rounded-xl bg-crimson/5 px-3 py-2 text-sm text-crimson"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {error}
        </p>
      ) : null}
      {notice ? (
        <p
          role="status"
          className="mt-6 rounded-xl border border-teal/25 bg-teal/5 px-3 py-2 text-sm text-fg-strong"
        >
          {notice}
        </p>
      ) : null}

      {issues === null ? (
        <div className="mt-8 space-y-4">
          {[0, 1].map((index) => (
            <div
              key={index}
              className="h-48 animate-pulse rounded-2xl border border-line bg-surface-2"
              aria-hidden
            />
          ))}
        </div>
      ) : issues.length === 0 ? (
        <div className="mt-8 rounded-2xl border border-dashed border-line-strong bg-surface p-12 text-center">
          <CheckCircle2 className="mx-auto h-8 w-8 text-teal" aria-hidden />
          <p className="mt-2 text-lg font-semibold">No client reports in your area</p>
          <p className="mt-1 text-sm text-fg-muted">
            New reports from districts covered by your organisation will appear here.
          </p>
        </div>
      ) : (
        <ul className="mt-8 space-y-4">
          {issues.map((issue) => (
            <li key={issue.report_id} className="card p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="max-w-3xl">
                  <p className="font-mono text-[11px] text-fg-subtle">
                    {issue.report_id} · {issue.district}
                    {issue.place ? ` · ${issue.place}` : ""} ·{" "}
                    {issue.reported_at.slice(0, 10)}
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-fg-strong">
                    {issue.report_text}
                  </p>
                  <p className="mt-2 text-xs capitalize text-fg-subtle">
                    Report severity: {issue.severity}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <Badge
                    tone={
                      issue.staff_response_status === "resolved"
                        ? "teal"
                        : issue.staff_response_status
                          ? "amber"
                          : "neutral"
                    }
                  >
                    {issue.staff_response_status
                      ? RESPONSE_LABELS[issue.staff_response_status]
                      : "Needs response"}
                  </Badge>
                  <span className="text-[11px] capitalize text-fg-subtle">
                    {issue.status}
                  </span>
                </div>
              </div>

              {issue.staff_response_text ? (
                <div className="mt-4 rounded-xl border border-line bg-surface-2 px-4 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                    Latest update sent to client
                    {issue.staff_responded_at
                      ? ` · ${issue.staff_responded_at.slice(0, 10)}`
                      : ""}
                  </p>
                  <p className="mt-1 text-sm leading-relaxed text-fg-soft">
                    {issue.staff_response_text}
                  </p>
                </div>
              ) : null}

              <IssueResponseForm
                busy={busyId === issue.report_id}
                initialStatus={issue.staff_response_status ?? "acknowledged"}
                onSubmit={(status, text) =>
                  handleResponse(issue.report_id, status, text)
                }
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function IssueResponseForm({
  busy,
  initialStatus,
  onSubmit,
}: {
  busy: boolean;
  initialStatus: StaffResponseStatus;
  onSubmit: (status: StaffResponseStatus, text: string) => Promise<boolean>;
}) {
  const [status, setStatus] = useState<StaffResponseStatus>(initialStatus);
  const [text, setText] = useState("");

  return (
    <form
      className="mt-4 flex flex-col gap-3 border-t border-line pt-4"
      onSubmit={(event) => {
        event.preventDefault();
        void onSubmit(status, text.trim()).then((saved) => {
          if (saved) setText("");
        });
      }}
    >
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs font-semibold text-fg-soft">
          Issue status
          <select
            value={status}
            onChange={(event) =>
              setStatus(event.target.value as StaffResponseStatus)
            }
            className="mt-1 block rounded-lg border border-line-strong bg-surface px-2.5 py-2 text-xs text-fg outline-none focus:border-teal"
          >
            {RESPONSE_STATUSES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="min-w-60 flex-1 text-xs font-semibold text-fg-soft">
          Message to the client
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            required
            minLength={1}
            maxLength={2000}
            rows={2}
            placeholder="Acknowledge the report or explain the action taken…"
            className="mt-1 block w-full resize-y rounded-lg border border-line-strong bg-surface px-3 py-2 text-sm font-normal text-fg outline-none focus:border-teal"
          />
        </label>
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-teal px-3.5 py-2.5 text-xs font-semibold text-white transition hover:bg-teal-deep disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Send className="h-3.5 w-3.5" aria-hidden />
          {busy ? "Sending…" : "Send update"}
        </button>
      </div>
    </form>
  );
}
