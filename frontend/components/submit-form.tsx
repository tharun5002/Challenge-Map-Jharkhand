"use client";

import { useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  Languages,
  Link2,
  MapPin,
  Send,
  ShieldCheck,
} from "lucide-react";
import { JHARKHAND_DISTRICT_NAMES } from "@/lib/data";
import { useI18n } from "@/components/locale-provider";
import { useSession } from "@/components/session-provider";
import {
  ApiError,
  getAccessToken,
  mergeComplaint,
  submitComplaint,
  type ApiComplaintSubmit,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Severity } from "@/lib/types";

const SEVERITIES: { id: Severity; label: string; hint: string }[] = [
  { id: "low", label: "Low", hint: "inconvenience" },
  { id: "medium", label: "Medium", hint: "service degraded" },
  { id: "high", label: "High", hint: "health or income at risk" },
  { id: "critical", label: "Critical", hint: "safety or survival" },
];

const COPY = {
  en: {
    label: "Your report",
    placeholder:
      "Describe the problem, where it is, and how long it has been going on. Example: the handpump near the primary school in ward 14 has been dry for three months…",
    district: "District",
    severity: "How serious is it?",
    affected: "How many people are affected? (optional)",
    submit: "Check and submit",
    note: "Your report is compared with non-merged reports in the same district using sparse TF-IDF cosine similarity. Candidates at or above 0.86 are shown to you before anything is merged — nothing is merged automatically.",
  },
  hi: {
    label: "आपकी शिकायत",
    placeholder:
      "समस्या क्या है, कहाँ है और कब से है — लिखिए। उदाहरण: वार्ड 14 के प्राथमिक विद्यालय के पास का हैंडपंप तीन महीने से सूखा है…",
    district: "ज़िला",
    severity: "कितनी गंभीर है?",
    affected: "कितने लोग प्रभावित हैं? (वैकल्पिक)",
    submit: "जाँचें और भेजें",
    note: "आपकी शिकायत उसी ज़िले की अन्य शिकायतों से TF-IDF समानता पर मिलाई जाती है। 0.86 या अधिक मिलने वाली शिकायतें आपको दिखाई जाती हैं — कुछ भी स्वयं नहीं जोड़ा जाता।",
  },
} as const;

type Phase = "form" | "review" | "done";
type Outcome = "new" | "attached" | null;

export function SubmitForm() {
  const { ready, user, signOut } = useSession();
  const { t } = useI18n();
  const [language, setLanguage] = useState<"en" | "hi">("en");
  const [text, setText] = useState("");
  const [district, setDistrict] = useState("Ranchi");
  const [severity, setSeverity] = useState<Severity>("high");
  const [affected, setAffected] = useState("");
  const [phase, setPhase] = useState<Phase>("form");
  const [result, setResult] = useState<ApiComplaintSubmit | null>(null);
  const [outcome, setOutcome] = useState<Outcome>(null);
  const [attachedTo, setAttachedTo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const copy = COPY[language];

  async function handleSubmit() {
    const token = getAccessToken();
    if (!token) {
      setError(t("submit.signInFirst"));
      return;
    }
    if (text.trim().length < 40) {
      setError("Please describe the problem in at least 40 characters.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await submitComplaint(
        {
          district,
          report_text: text.trim(),
          language: language === "hi" ? "hi" : "en",
          severity,
          affected_population:
            affected.trim() === "" ? null : Number(affected),
        },
        token,
      );
      setResult(created);
      setOutcome("new");
      setPhase(created.duplicate_candidates.length > 0 ? "review" : "done");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : t("submit.apiOffline"),
      );
    } finally {
      setBusy(false);
    }
  }

  async function attachTo(candidateId: string) {
    const token = getAccessToken();
    if (!token || !result) return;
    setBusy(true);
    setError(null);
    try {
      await mergeComplaint(result.report_id, candidateId, token);
      setAttachedTo(candidateId);
      setOutcome("attached");
      setPhase("done");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : t("submit.apiOffline"),
      );
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setPhase("form");
    setResult(null);
    setOutcome(null);
    setAttachedTo(null);
    setText("");
    setAffected("");
    setError(null);
  }

  if (!ready) {
    return (
      <div
        className="mt-10 h-48 animate-pulse rounded-2xl border border-line bg-surface-2"
        aria-hidden
      />
    );
  }

  if (!user) {
    return (
      <div className="mt-10 max-w-2xl rounded-2xl border border-line bg-surface p-8 shadow-card">
        <h2 className="text-xl font-bold tracking-tight">
          {t("submit.signInFirst")}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-fg-muted">
          {t("submit.signInHint")}
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/login"
            className="rounded-xl bg-teal px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-deep"
          >
            {t("nav.signIn")}
          </Link>
          <Link
            href="/register"
            className="rounded-xl border border-line-strong px-4 py-2.5 text-sm font-semibold text-fg-strong hover:bg-fg/5"
          >
            {t("auth.createOne")}
          </Link>
        </div>
      </div>
    );
  }

  // The API restricts submissions to the citizen role so every report has an
  // accountable owner. Say so here instead of failing after the form is filled.
  if (user.role !== "citizen") {
    return (
      <div className="mt-10 max-w-2xl rounded-2xl border border-line bg-surface p-8 shadow-card">
        <h2 className="text-xl font-bold tracking-tight">
          Citizen reports use citizen accounts
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-fg-muted">
          You are signed in as <strong>{user.username}</strong> ({user.role}). The
          API accepts submissions from the citizen role, so this form is disabled
          for {user.role} accounts. Sign out and sign in with a citizen account to
          file a report.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={signOut}
            className="rounded-xl bg-teal px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-deep"
          >
            Sign out
          </button>
          <Link
            href={user.role === "admin" ? "/admin" : "/partners/dashboard"}
            className="rounded-xl border border-line-strong px-4 py-2.5 text-sm font-semibold text-fg-strong hover:bg-fg/5"
          >
            {user.role === "admin" ? "Open the admin console" : "Open partner portal"}
          </Link>
        </div>
      </div>
    );
  }

  if (phase === "done" && result) {
    const attached = outcome === "attached";
    return (
      <div className="mt-10 max-w-2xl rounded-2xl border border-teal/25 bg-surface p-8 shadow-card">
        <span className="grid h-12 w-12 place-items-center rounded-full bg-teal/10 text-teal">
          {attached ? (
            <Link2 className="h-6 w-6" aria-hidden />
          ) : (
            <CheckCircle2 className="h-6 w-6" aria-hidden />
          )}
        </span>
        <h2 className="mt-4 text-xl font-bold tracking-tight">
          {attached ? "Added to an existing report" : "Report received"}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-fg-soft">
          {attached ? (
            <>
              Your report <strong>{result.report_id}</strong> was merged into{" "}
              <strong>{attachedTo}</strong>. It will be counted once in its
              cluster — no duplicate challenge was created.
            </>
          ) : (
            <>
              Reference <strong>{result.report_id}</strong>. It is queued for
              automatic clustering, which groups it with similar reports; an
              administrator reviews the cluster before publishing a brief.
            </>
          )}
        </p>
        <p className="mt-3 rounded-lg bg-surface-2 px-3 py-2 text-[11px] leading-relaxed text-fg-muted">
          Status: {attached ? "merged" : result.status} · District:{" "}
          {result.district} · Reported {result.reported_at.slice(0, 10)}
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/challenges"
            className="rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white"
          >
            Browse challenges
          </Link>
          <button
            type="button"
            onClick={reset}
            className="rounded-xl border border-line-strong px-4 py-2.5 text-sm font-semibold text-fg-strong"
          >
            Report another issue
          </button>
        </div>
      </div>
    );
  }

  if (phase === "review" && result) {
    const candidates = result.duplicate_candidates;
    return (
      <div className="mt-10 max-w-2xl">
        <div className="card p-6">
          <p className="eyebrow">Duplicate check</p>
          <h2 className="mt-1 text-xl font-bold tracking-tight">
            {candidates.length} similar{" "}
            {candidates.length === 1 ? "report" : "reports"} found in{" "}
            {result.district}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-fg-soft">
            Your report <strong>{result.report_id}</strong> is saved. Attach it to
            an existing report so the same problem is counted once, or keep it as
            a separate report.
          </p>

          <ul className="mt-5 space-y-3">
            {candidates.map((candidate) => (
              <li
                key={candidate.report_id}
                className="rounded-xl border border-line bg-surface-2 p-4"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-fg-soft">
                    <MapPin className="h-3 w-3 text-fg-subtle" aria-hidden />
                    {candidate.report_id} · {candidate.district}
                  </span>
                  <span className="rounded-md bg-surface px-1.5 py-0.5 text-[11px] font-bold text-teal">
                    {(candidate.similarity * 100).toFixed(0)}% similar
                  </span>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-fg-strong">
                  {candidate.report_text}
                </p>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => attachTo(candidate.report_id)}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-teal px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-deep disabled:opacity-60"
                >
                  <Link2 className="h-3.5 w-3.5" aria-hidden />
                  Attach to this report
                </button>
              </li>
            ))}
          </ul>

          {error ? (
            <p
              role="alert"
              className="mt-4 flex items-start gap-2 rounded-xl bg-crimson/5 px-3 py-2 text-sm text-crimson"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              {error}
            </p>
          ) : null}

          <button
            type="button"
            disabled={busy}
            onClick={() => setPhase("done")}
            className="mt-5 w-full rounded-xl border border-line-strong px-4 py-2.5 text-sm font-semibold text-fg-strong hover:bg-fg/5 disabled:opacity-60"
          >
            Keep as a separate report
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-10 grid gap-6 lg:grid-cols-[1.15fr_0.85fr] lg:items-start">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void handleSubmit();
        }}
        className="card p-6 sm:p-7"
      >
        <div className="flex items-center justify-between gap-3">
          <label htmlFor="report-text" className="text-sm font-semibold text-fg">
            {copy.label}
          </label>
          <div className="flex items-center gap-1 rounded-lg border border-line bg-surface-2 p-0.5">
            <Languages className="ml-1.5 h-3.5 w-3.5 text-fg-subtle" aria-hidden />
            {(["en", "hi"] as const).map((code) => (
              <button
                key={code}
                type="button"
                onClick={() => setLanguage(code)}
                className={cn(
                  "rounded-md px-2 py-1 text-[11px] font-semibold transition",
                  language === code
                    ? "bg-surface text-fg shadow-sm"
                    : "text-fg-muted",
                )}
                aria-pressed={language === code}
              >
                {code === "en" ? "English" : "हिंदी"}
              </button>
            ))}
          </div>
        </div>

        <textarea
          id="report-text"
          aria-describedby="report-text-hint"
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={6}
          placeholder={copy.placeholder}
          lang={language === "hi" ? "hi" : "en"}
          className="mt-2 w-full resize-y rounded-xl border border-line-strong bg-surface-2 p-4 text-sm leading-relaxed outline-none transition placeholder:text-fg-subtle focus:border-teal focus:bg-surface"
        />
        <div
          id="report-text-hint"
          className="mt-1.5 flex justify-between text-[11px] text-fg-subtle"
        >
          <span>Minimum 40 characters</span>
          <span>{text.trim().length} / 40+</span>
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <Field label={copy.district} htmlFor="district">
            <select
              id="district"
              value={district}
              onChange={(event) => setDistrict(event.target.value)}
              className="w-full rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm outline-none focus:border-teal"
            >
              {JHARKHAND_DISTRICT_NAMES.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </Field>

          <Field label={copy.affected} htmlFor="affected">
            <input
              id="affected"
              type="number"
              min={0}
              inputMode="numeric"
              value={affected}
              onChange={(event) => setAffected(event.target.value)}
              placeholder="e.g. 1200"
              className="w-full rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm outline-none focus:border-teal"
            />
          </Field>
        </div>

        <fieldset className="mt-5">
          <legend className="text-sm font-semibold text-fg">
            {copy.severity}
          </legend>
          <div className="mt-2 grid gap-2 sm:grid-cols-4">
            {SEVERITIES.map((option) => (
              <label
                key={option.id}
                className={cn(
                  "cursor-pointer rounded-xl border px-3 py-2 text-center transition",
                  severity === option.id
                    ? "border-teal bg-teal/5 ring-1 ring-teal"
                    : "border-line bg-surface hover:border-line-strong",
                )}
              >
                <input
                  type="radio"
                  name="severity"
                  value={option.id}
                  checked={severity === option.id}
                  onChange={() => setSeverity(option.id)}
                  className="sr-only"
                />
                <span className="block text-xs font-bold capitalize text-fg">
                  {option.label}
                </span>
                <span className="mt-0.5 block text-[10px] leading-tight text-fg-subtle">
                  {option.hint}
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        {error ? (
          <p
            role="alert"
            className="mt-4 flex items-start gap-2 rounded-xl bg-crimson/5 px-3 py-2 text-sm text-crimson"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={busy}
          className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-teal px-4 py-3 text-sm font-semibold text-white transition hover:bg-teal-deep disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Send className="h-4 w-4" aria-hidden />
          {busy ? "Sending…" : copy.submit}
        </button>

        <p className="mt-3 text-[11px] leading-relaxed text-fg-subtle">
          Do not include names, phone numbers or ID numbers. Bulk-ingested data is
          scrubbed automatically, but reports filed here are stored as written and
          can appear as evidence quotes.
        </p>
      </form>

      <aside className="lg:sticky lg:top-24">
        <div className="card p-6">
          <h2 className="text-sm font-bold text-fg">How duplicates are handled</h2>
          <ul className="mt-3 space-y-3 text-xs leading-relaxed text-fg-soft">
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-teal" aria-hidden />
              Your report is saved first, then compared with other reports in the
              same district.
            </li>
            <li className="flex gap-2">
              <Link2 className="mt-0.5 h-4 w-4 shrink-0 text-teal" aria-hidden />
              Nothing merges automatically. You choose whether to attach.
            </li>
            <li className="flex gap-2">
              <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-teal" aria-hidden />
              Matching is district-blocked, so a water complaint in Ranchi is never
              merged with one in Palamu.
            </li>
          </ul>
          <p className="mt-4 border-t border-line pt-3 text-[11px] leading-relaxed text-fg-subtle">
            {copy.note}
          </p>
        </div>

        <div className="mt-4 rounded-2xl border border-line bg-surface-2 p-4">
          <p className="text-[11px] leading-relaxed text-fg-muted">
            Signed in as{" "}
            <strong className="text-fg-strong">
              {user.full_name || user.username}
            </strong>
            . Reports are tied to your account so merges and follow-ups reach you.
          </p>
        </div>
      </aside>
    </div>
  );
}

function Field({
  label,
  htmlFor,
  children,
  className,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className="text-sm font-semibold text-fg">
        {label}
      </label>
      <div className="mt-1.5">{children}</div>
    </div>
  );
}
