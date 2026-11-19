"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, MessageSquare, Send } from "lucide-react";
import { RoleGate } from "@/components/role-gate";
import { CITIZEN_ONLY } from "@/lib/roles";
import {
  ApiError,
  fetchFeedback,
  getAccessToken,
  listMyComplaints,
  submitFeedback,
  type ApiComplaint,
  type ApiFeedback,
} from "@/lib/api";
import { Badge } from "@/components/ui";

const STATUSES = ["Not solved", "Partially solved", "Solved"] as const;
type FeedbackStatus = (typeof STATUSES)[number];

const STATUS_TONE: Record<string, "amber" | "teal" | "neutral" | "crimson"> = {
  pending: "amber",
  clustered: "teal",
  merged: "neutral",
  rejected: "crimson",
};

export default function ReportsPage() {
  return (
    <RoleGate
      allow={CITIZEN_ONLY}
      signedOutTitle="My reports"
      signedOutHint="Sign in to see the reports you filed and record whether the problem was solved."
      deniedTitle="Citizen reports"
    >
      {() => <CitizenReports />}
    </RoleGate>
  );
}

function CitizenReports() {
  const [reports, setReports] = useState<ApiComplaint[] | null>(null);
  const [feedback, setFeedback] = useState<Record<string, ApiFeedback[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setError(null);
    try {
      const rows = await listMyComplaints(token);
      setReports(rows);
      const histories = await Promise.all(
        rows.map(
          async (row) =>
            [row.report_id, await fetchFeedback(row.report_id, token)] as const,
        ),
      );
      setFeedback(Object.fromEntries(histories));
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not reach the API. Start the service and try again.",
      );
      setReports([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleFeedback(
    reportId: string,
    status: FeedbackStatus,
    text: string,
  ): Promise<boolean> {
    const token = getAccessToken();
    if (!token) return false;
    try {
      const created = await submitFeedback(
        reportId,
        { status, feedback_text: text },
        token,
      );
      setFeedback((current) => ({
        ...current,
        [reportId]: [created, ...(current[reportId] ?? [])],
      }));
      setNotice(`Feedback recorded for ${reportId}: ${created.status}.`);
      return true;
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Could not record feedback.",
      );
      return false;
    }
  }

  return (
    <div className="shell py-10 sm:py-14">
      <div className="max-w-3xl">
        <p className="eyebrow">Citizen account</p>
        <h1 className="h1 mt-2 text-3xl sm:text-4xl">My reports</h1>
        <p className="lede mt-3">
          Every report you filed, its current clustering status, and the feedback you
          have recorded. A report you attached to another one keeps its own reference
          and is marked merged, so it is counted once in that cluster.
        </p>
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

      {reports === null ? (
        <div
          className="mt-8 h-52 animate-pulse rounded-2xl border border-line bg-surface-2"
          aria-hidden
        />
      ) : reports.length === 0 ? (
        <div className="mt-8 rounded-2xl border border-dashed border-line-strong bg-surface p-12 text-center">
          <MessageSquare className="mx-auto h-8 w-8 text-teal" aria-hidden />
          <p className="mt-2 text-lg font-semibold">No reports filed yet</p>
          <p className="mt-1 text-sm text-fg-muted">
            Report a problem and it will appear here with its clustering status.
          </p>
          <Link
            href="/submit"
            className="mt-4 inline-flex rounded-xl bg-teal px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-deep"
          >
            Report an issue
          </Link>
        </div>
      ) : (
        <ul className="mt-8 space-y-4">
          {reports.map((report) => (
            <li key={report.report_id} className="card p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="max-w-2xl">
                  <p className="font-mono text-[11px] text-fg-subtle">
                    {report.report_id} · {report.district} ·{" "}
                    {report.reported_at.slice(0, 10)}
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-fg-strong">
                    {report.report_text}
                  </p>
                </div>
                <div className="text-right">
                  <Badge tone={STATUS_TONE[report.status] ?? "neutral"}>
                    {report.status}
                  </Badge>
                  {report.duplicate_of ? (
                    <p className="mt-1 font-mono text-[10px] text-fg-subtle">
                      attached to {report.duplicate_of}
                    </p>
                  ) : null}
                </div>
              </div>

              {feedback[report.report_id]?.length ? (
                <ul className="mt-4 space-y-1.5 border-t border-line pt-3">
                  {feedback[report.report_id].map((entry) => (
                    <li key={entry.feedback_id} className="text-xs text-fg-soft">
                      <strong className="font-semibold">{entry.status}</strong>
                      {entry.feedback_text ? ` — ${entry.feedback_text}` : ""}
                      <span className="ml-1 text-fg-subtle">
                        ({entry.submitted_at.slice(0, 10)})
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}

              {report.staff_response_text ? (
                <div className="mt-4 rounded-xl border border-teal/20 bg-teal/5 px-4 py-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-teal-deep">
                    Staff update
                    {report.staff_response_status
                      ? ` · ${report.staff_response_status.replace(/_/g, " ")}`
                      : ""}
                    {report.staff_responded_at
                      ? ` · ${report.staff_responded_at.slice(0, 10)}`
                      : ""}
                  </p>
                  <p className="mt-1 text-sm leading-relaxed text-fg-strong">
                    {report.staff_response_text}
                  </p>
                </div>
              ) : null}

              {report.status === "merged" || report.status === "rejected" ? null : (
                <FeedbackForm
                  onSubmit={(status, text) =>
                    handleFeedback(report.report_id, status, text)
                  }
                />
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function FeedbackForm({
  onSubmit,
}: {
  onSubmit: (status: FeedbackStatus, text: string) => Promise<boolean>;
}) {
  const [status, setStatus] = useState<FeedbackStatus>("Not solved");
  const [text, setText] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  if (sent) {
    return (
      <p
        role="status"
        className="mt-4 flex items-center gap-2 rounded-xl bg-teal/5 px-3 py-2 text-xs text-fg-strong"
      >
        <CheckCircle2 className="h-4 w-4 text-teal" aria-hidden />
        Feedback saved.
      </p>
    );
  }

  return (
    <form
      className="mt-4 flex flex-col gap-2 border-t border-line pt-3 sm:flex-row sm:items-end"
      onSubmit={(event) => {
        event.preventDefault();
        setBusy(true);
        void onSubmit(status, text.trim()).then((saved) => {
          if (saved) setSent(true);
          setBusy(false);
        });
      }}
    >
      <label className="text-xs font-semibold text-fg-soft">
        Resolution
        <select
          value={status}
          onChange={(event) => setStatus(event.target.value as FeedbackStatus)}
          className="mt-1 block w-full rounded-lg border border-line-strong bg-surface px-2.5 py-1.5 text-xs text-fg outline-none focus:border-teal sm:w-44"
        >
          {STATUSES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
      <label className="flex-1 text-xs font-semibold text-fg-soft">
        Comment (optional)
        <input
          value={text}
          onChange={(event) => setText(event.target.value)}
          maxLength={2000}
          placeholder="What changed, if anything?"
          className="mt-1 block w-full rounded-lg border border-line-strong bg-surface px-2.5 py-1.5 text-xs text-fg outline-none focus:border-teal"
        />
      </label>
      <button
        type="submit"
        disabled={busy}
        className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-line-strong px-3 py-1.5 text-xs font-semibold text-fg-strong hover:bg-fg/5 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <Send className="h-3.5 w-3.5" aria-hidden />
        {busy ? "Saving…" : "Send feedback"}
      </button>
    </form>
  );
}
