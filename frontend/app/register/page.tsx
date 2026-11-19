"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertTriangle, CheckCircle2, UserPlus } from "lucide-react";
import { JHARKHAND_DISTRICT_NAMES } from "@/lib/data";
import { useI18n } from "@/components/locale-provider";
import { useSession } from "@/components/session-provider";
import { ApiError, registerPartnerAccount } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const { t } = useI18n();
  const { signUp } = useSession();
  const [accountType, setAccountType] = useState<"citizen" | "partner">("citizen");
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [district, setDistrict] = useState("Ranchi");
  const [organizationName, setOrganizationName] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [partnerRequestSubmitted, setPartnerRequestSubmitted] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password.length < 12) {
      setError("Password must be at least 12 characters.");
      return;
    }
    if (password !== confirm) {
      setError("The passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (accountType === "partner") {
        await registerPartnerAccount({
          username: username.trim(),
          email: email.trim(),
          password,
          full_name: fullName.trim(),
          district,
          organization_name: organizationName.trim(),
          job_title: jobTitle.trim(),
        });
        setPartnerRequestSubmitted(true);
        return;
      }
      await signUp({
        username: username.trim(),
        email: email.trim(),
        password,
        full_name: fullName.trim(),
        district,
      });
      router.replace("/submit");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : t("auth.errorGeneric"),
      );
      setBusy(false);
    }
  }

  return (
    <div className="shell flex min-h-[70vh] items-center justify-center py-12">
      <div className="w-full max-w-xl">
        <div className="card p-7">
          <h1 className="text-2xl font-extrabold tracking-tight">
            {t("auth.registerTitle")}
          </h1>
          <p className="mt-1 text-sm text-fg-muted">{t("auth.registerLead")}</p>

          {partnerRequestSubmitted ? (
            <div
              role="status"
              className="mt-5 flex items-start gap-3 rounded-xl border border-teal/20 bg-teal/5 p-4 text-sm text-fg"
            >
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-teal" aria-hidden />
              <p>{t("auth.partnerRequestSubmitted")}</p>
            </div>
          ) : (
            <>
              <div role="group" aria-label={t("auth.signupType")} className="mt-5">
                <p className="mb-1.5 text-sm font-semibold text-fg">
                  {t("auth.signupType")}
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {(["citizen", "partner"] as const).map((type) => (
                    <button
                      key={type}
                      type="button"
                      aria-pressed={accountType === type}
                      onClick={() => {
                        setAccountType(type);
                        setError(null);
                      }}
                      className={`rounded-xl border px-3 py-2.5 text-sm font-semibold transition ${
                        accountType === type
                          ? "border-teal bg-teal/5 text-teal"
                          : "border-line-strong text-fg-muted hover:bg-surface-2"
                      }`}
                    >
                      {t(type === "citizen" ? "auth.roleCitizen" : "auth.rolePartner")}
                    </button>
                  ))}
                </div>
              </div>

          <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="name" className="text-sm font-semibold text-fg">
                  {t("auth.fullName")}
                </label>
                <input
                  id="name"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  autoComplete="name"
                  className="mt-1.5 w-full rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm outline-none focus:border-teal"
                />
              </div>
              <div>
                <label htmlFor="district" className="text-sm font-semibold text-fg">
                  {t("auth.district")}
                </label>
                <select
                  id="district"
                  value={district}
                  onChange={(event) => setDistrict(event.target.value)}
                  className="mt-1.5 w-full rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm outline-none focus:border-teal"
                >
                  {JHARKHAND_DISTRICT_NAMES.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {accountType === "partner" ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="organization-name" className="text-sm font-semibold text-fg">
                    {t("auth.organizationName")}
                  </label>
                  <input
                    id="organization-name"
                    required
                    maxLength={160}
                    value={organizationName}
                    onChange={(event) => setOrganizationName(event.target.value)}
                    autoComplete="organization"
                    className="mt-1.5 w-full rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm outline-none focus:border-teal"
                  />
                </div>
                <div>
                  <label htmlFor="job-title" className="text-sm font-semibold text-fg">
                    {t("auth.jobTitle")}
                  </label>
                  <input
                    id="job-title"
                    required
                    maxLength={120}
                    value={jobTitle}
                    onChange={(event) => setJobTitle(event.target.value)}
                    autoComplete="organization-title"
                    className="mt-1.5 w-full rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm outline-none focus:border-teal"
                  />
                </div>
              </div>
            ) : null}

            <div>
              <label htmlFor="email" className="text-sm font-semibold text-fg">
                {t("auth.emailAddress")}
              </label>
              <input
                id="email"
                type="email"
                required
                maxLength={254}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                autoCapitalize="none"
                spellCheck={false}
                className="mt-1.5 w-full rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm outline-none focus:border-teal"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="username" className="text-sm font-semibold text-fg">
                {t("auth.username")}
              </label>
              <input
                id="username"
                required
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                aria-describedby="username-hint"
                className="mt-1.5 w-full rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm outline-none focus:border-teal"
                placeholder="your.username"
              />
              <p id="username-hint" className="mt-1 text-[11px] text-fg-subtle">
                {t("auth.usernameHint")}
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="password" className="text-sm font-semibold text-fg">
                  {t("auth.password")}
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  minLength={12}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="new-password"
                  aria-describedby="password-hint"
                  className="mt-1.5 w-full rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm outline-none focus:border-teal"
                />
              </div>
              <div>
                <label htmlFor="confirm" className="text-sm font-semibold text-fg">
                  {t("auth.confirmPassword")}
                </label>
                <input
                  id="confirm"
                  type="password"
                  required
                  minLength={12}
                  value={confirm}
                  onChange={(event) => setConfirm(event.target.value)}
                  autoComplete="new-password"
                  aria-describedby="password-hint"
                  className="mt-1.5 w-full rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm outline-none focus:border-teal"
                />
              </div>
            </div>
            <p id="password-hint" className="text-[11px] text-fg-subtle">
              {t("auth.passwordHint")}
            </p>

            {error ? (
              <p
                role="alert"
                className="flex items-start gap-2 rounded-xl bg-crimson/5 px-3 py-2 text-sm text-crimson"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                {error}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={busy}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-teal px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-deep disabled:cursor-not-allowed disabled:opacity-60"
            >
              <UserPlus className="h-4 w-4" aria-hidden />
              {busy
                ? accountType === "partner"
                  ? t("auth.partnerRequesting")
                  : t("auth.creating")
                : accountType === "partner"
                  ? t("auth.partnerRequestCta")
                  : t("auth.createCitizen")}
            </button>
          </form>

          <p className="mt-4 rounded-xl bg-surface-2 px-3 py-2 text-[11px] leading-relaxed text-fg-muted">
            {t("auth.partnerNote")}
          </p>
            </>
          )}

          <p className="mt-5 text-center text-sm text-fg-muted">
            {t("auth.alreadyRegistered")}{" "}
            <Link href="/login" className="font-semibold text-teal hover:underline">
              {t("auth.signInCta")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
