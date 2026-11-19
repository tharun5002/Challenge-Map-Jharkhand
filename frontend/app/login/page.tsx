"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertTriangle, LogIn, MapPinned } from "lucide-react";
import { useI18n } from "@/components/locale-provider";
import { useSession } from "@/components/session-provider";
import { ApiError, type ApiRole } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { t } = useI18n();
  const { signIn } = useSession();
  const [role, setRole] = useState<ApiRole>("citizen");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await signIn(email.trim(), password, role);
      router.replace(
        user.role === "admin"
          ? "/admin"
          : user.role === "partner"
            ? "/partners/dashboard"
            : "/submit",
      );
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.status === 422
            ? t("auth.loginApiOutdated")
            : caught.message
          : t("auth.errorGeneric"),
      );
      setBusy(false);
    }
  }

  return (
    <div className="shell flex min-h-[70vh] items-center justify-center py-12">
      <div className="w-full max-w-md">
        <div className="card p-7">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-ink text-teal-bright">
            <MapPinned className="h-5 w-5" aria-hidden />
          </span>
          <h1 className="mt-4 text-2xl font-extrabold tracking-tight">
            {t("auth.signInTitle")}
          </h1>
          <p className="mt-1 text-sm text-fg-muted">{t("auth.signInLead")}</p>

          <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
            <div>
              <fieldset>
                <legend className="text-sm font-semibold text-fg">
                  {t("auth.signInAs")}
                </legend>
                <div className="mt-2 grid grid-cols-3 gap-2">
                  {([
                    ["citizen", t("auth.roleCitizen")],
                    ["partner", t("auth.roleStaff")],
                    ["admin", t("auth.roleAdmin")],
                  ] as const).map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      aria-pressed={role === value}
                      onClick={() => setRole(value)}
                      className={`rounded-lg border px-2 py-2 text-sm font-semibold transition ${
                        role === value
                          ? "border-teal bg-teal/10 text-teal"
                          : "border-line-strong text-fg-muted hover:text-fg"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </fieldset>
            </div>
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
              <p className="mt-1 text-[11px] text-fg-subtle">
                {t("auth.emailOnlyHint")}
              </p>
            </div>
            <div>
              <label htmlFor="password" className="text-sm font-semibold text-fg">
                {t("auth.password")}
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                className="mt-1.5 w-full rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm outline-none focus:border-teal"
              />
            </div>

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
              <LogIn className="h-4 w-4" aria-hidden />
              {busy ? t("auth.signingIn") : t("auth.signInCta")}
            </button>
          </form>

          <p className="mt-5 text-center text-sm text-fg-muted">
            {t("auth.noAccount")}{" "}
            <Link href="/register" className="font-semibold text-teal hover:underline">
              {t("auth.createOne")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
