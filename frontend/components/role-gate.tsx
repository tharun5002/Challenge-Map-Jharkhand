"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ShieldAlert } from "lucide-react";
import { useSession } from "@/components/session-provider";
import type { ApiRole, ApiUser } from "@/lib/api";
import { ROLE_LABELS, accountHome } from "@/lib/roles";

type RoleGateProps = {
  allow: readonly ApiRole[];
  signedOutTitle: string;
  signedOutHint: string;
  deniedTitle?: string;
  children: (user: ApiUser) => ReactNode;
};

/**
 * Renders a page only for the listed roles.
 *
 * Signed-out visitors get a sign-in card and the wrong role gets a pointer to
 * its own account home instead of a broken page. The API re-checks the role on
 * every request, so this is presentation, not enforcement.
 */
export function RoleGate({
  allow,
  signedOutTitle,
  signedOutHint,
  deniedTitle = "This page needs a different account",
  children,
}: RoleGateProps) {
  const { user, ready } = useSession();

  if (!ready) {
    return (
      <div className="shell py-14">
        <div
          className="h-40 animate-pulse rounded-2xl border border-line bg-surface-2"
          aria-hidden
        />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="shell py-14">
        <div className="max-w-lg rounded-2xl border border-line bg-surface p-8 shadow-card">
          <h1 className="text-2xl font-extrabold tracking-tight">{signedOutTitle}</h1>
          <p className="mt-2 text-sm leading-relaxed text-fg-muted">{signedOutHint}</p>
          <Link
            href="/login"
            className="mt-6 inline-flex rounded-xl bg-teal px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-deep"
          >
            Sign in
          </Link>
        </div>
      </div>
    );
  }

  if (!allow.includes(user.role)) {
    return (
      <div className="shell py-14">
        <div className="max-w-lg rounded-2xl border border-line bg-surface p-8 shadow-card">
          <ShieldAlert className="h-6 w-6 text-crimson" aria-hidden />
          <h1 className="mt-3 text-2xl font-extrabold tracking-tight">{deniedTitle}</h1>
          <p className="mt-2 text-sm leading-relaxed text-fg-muted">
            You are signed in as <strong>{user.username}</strong> (
            {ROLE_LABELS[user.role]}). This page is open to{" "}
            {allow.map((role) => ROLE_LABELS[role]).join(" or ")} accounts.
          </p>
          <Link
            href={accountHome(user.role)}
            className="mt-6 inline-flex rounded-xl bg-teal px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-deep"
          >
            Go to your account
          </Link>
        </div>
      </div>
    );
  }

  return <>{children(user)}</>;
}
