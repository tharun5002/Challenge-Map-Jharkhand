"use client";

import { useCallback, useEffect, useState } from "react";
import { Building2, Check, Handshake, MapPin } from "lucide-react";
import { RoleGate } from "@/components/role-gate";
import { PARTNER_ONLY } from "@/lib/roles";
import {
  ApiError,
  expressInterest,
  fetchPartnerMatches,
  getAccessToken,
  type ApiMatch,
  type ApiUser,
} from "@/lib/api";
import { Badge } from "@/components/ui";

const COMPONENT_LABELS: Record<string, string> = {
  tag_overlap: "Capability overlap",
  district_proximity: "District proximity",
  severity: "Severity alignment",
  capacity: "Partner capacity",
};

const STATUS_LABEL: Record<ApiMatch["status"], string> = {
  suggested: "Awaiting your response",
  expressed_interest: "Interest recorded",
  confirmed: "Confirmed by administrator",
  declined: "Declined",
};

export default function PartnerDashboardPage() {
  return (
    <RoleGate
      allow={PARTNER_ONLY}
      signedOutTitle="Partner portal"
      signedOutHint="Matched challenges are visible to the organisation they were routed to. Sign in with a staff account to see yours."
      deniedTitle="Partner access required"
    >
      {(user) => <PartnerDashboard user={user} />}
    </RoleGate>
  );
}

function PartnerDashboard({ user }: { user: ApiUser }) {
  const [matches, setMatches] = useState<ApiMatch[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    setError(null);
    try {
      setMatches(await fetchPartnerMatches(token));
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not reach the partner API. Start the API service and try again.",
      );
      setMatches([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleInterest(match: ApiMatch) {
    const token = getAccessToken();
    if (!token) return;
    setBusyId(match.id);
    setError(null);
    try {
      const updated = await expressInterest(match.id, token);
      setMatches((current) =>
        current?.map((item) => (item.id === updated.id ? updated : item)) ?? current,
      );
      setNotice(`Interest recorded for “${updated.challenge_title}”.`);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Could not record interest.",
      );
    } finally {
      setBusyId(null);
    }
  }

  const list = matches ?? [];
  const awaiting = list.filter((match) => match.status === "suggested").length;
  const interested = list.filter(
    (match) => match.status === "expressed_interest",
  ).length;

  return (
    <div className="shell py-10 sm:py-14">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Partner portal</p>
          <h1 className="h1 mt-2 text-3xl sm:text-4xl">
            Challenges matched to your organisation
          </h1>
          <p className="mt-2 inline-flex items-center gap-1.5 text-sm text-fg-muted">
            <Building2 className="h-4 w-4" aria-hidden />
            {user.full_name || user.username} · matched by capability tags, district
            coverage and capacity
          </p>
        </div>
        <Badge tone="teal">
          <Check className="h-3.5 w-3.5" aria-hidden />
          Partner account
        </Badge>
      </div>

      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        {[
          { label: "Matched challenges", value: list.length },
          { label: "Awaiting your response", value: awaiting },
          { label: "Expressed interest", value: interested },
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
          className="mt-6 rounded-xl bg-crimson/5 px-3 py-2 text-sm text-crimson"
        >
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

      {matches === null ? (
        <div className="mt-8 space-y-4">
          {[0, 1].map((index) => (
            <div
              key={index}
              className="h-44 animate-pulse rounded-2xl border border-line bg-surface-2"
              aria-hidden
            />
          ))}
        </div>
      ) : list.length === 0 ? (
        <div className="mt-8 rounded-2xl border border-dashed border-line-strong bg-surface p-12 text-center">
          <p className="text-lg font-semibold">No matches yet</p>
          <p className="mt-1 text-sm text-fg-muted">
            Matches appear once an administrator publishes a challenge that overlaps
            your capability tags and districts.
          </p>
        </div>
      ) : (
        <ul className="mt-8 space-y-4">
          {list.map((match) => {
            const components = match.breakdown?.components ?? {};
            return (
              <li key={match.id} className="card p-6">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="max-w-2xl">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={match.status === "suggested" ? "amber" : "teal"}>
                        {STATUS_LABEL[match.status]}
                      </Badge>
                      <span className="text-[11px] text-fg-subtle">
                        Challenge #{match.challenge_slug.slice(0, 8)}
                      </span>
                    </div>
                    <h2 className="mt-2 text-[17px] font-bold leading-snug tracking-tight">
                      {match.challenge_title}
                    </h2>
                    <p className="mt-1.5 inline-flex items-center gap-1.5 text-xs text-fg-subtle">
                      <MapPin className="h-3 w-3" aria-hidden />
                      {match.organization_name}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                      Match score
                    </p>
                    <p className="text-2xl font-extrabold tracking-tight text-teal">
                      {match.score.toFixed(2)}
                    </p>
                  </div>
                </div>

                {Object.keys(components).length > 0 ? (
                  <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    {Object.entries(components).map(([key, value]) => (
                      <div key={key} className="rounded-lg bg-surface-2 px-3 py-2">
                        <div className="flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-fg-subtle">
                          <span>{COMPONENT_LABELS[key] ?? key}</span>
                          <span className="text-fg-strong">{value.toFixed(2)}</span>
                        </div>
                        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-fg/10">
                          <div
                            className="h-full rounded-full bg-teal"
                            style={{ width: `${Math.round(value * 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}

                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
                  <p className="text-[11px] text-fg-subtle">
                    The score breakdown is computed by the matching engine and stored
                    with the match — nothing here is inferred in the browser.
                  </p>
                  {match.status === "expressed_interest" ||
                  match.status === "confirmed" ? (
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-teal/25 bg-teal/10 px-3 py-1.5 text-xs font-semibold text-teal-deep">
                      <Handshake className="h-3.5 w-3.5" aria-hidden />
                      {match.status === "confirmed"
                        ? "Confirmed by administrator"
                        : "Interest recorded"}
                    </span>
                  ) : match.status === "declined" ? (
                    <span className="rounded-full border border-line bg-fg/5 px-3 py-1.5 text-xs font-semibold text-fg-muted">
                      Declined
                    </span>
                  ) : (
                    <button
                      type="button"
                      disabled={busyId === match.id}
                      onClick={() => void handleInterest(match)}
                      className="rounded-xl bg-teal px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-teal-deep disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {busyId === match.id ? "Recording…" : "Express interest"}
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
