/**
 * One place where role capabilities live.
 *
 * The API is the enforcement point (api/deps.py); this map only decides what the
 * interface offers. When a control is added here, the matching endpoint must
 * already reject the other roles.
 */

import type { ApiRole } from "@/lib/api";

export type Capability =
  | "complaints:submit"
  | "complaints:feedback"
  | "partner:matches"
  | "admin:console"
  | "admin:users";

const CAPABILITIES: Record<ApiRole, readonly Capability[]> = {
  citizen: ["complaints:submit", "complaints:feedback"],
  partner: ["partner:matches"],
  admin: ["admin:console", "admin:users"],
};

export const ROLE_LABELS: Record<ApiRole, string> = {
  citizen: "Citizen",
  partner: "Staff",
  admin: "Administrator",
};

export const ROLE_HINTS: Record<ApiRole, string> = {
  citizen: "files reports and tracks their resolution",
  partner: "responds to citizen reports and reviews matched challenges",
  admin: "runs clustering, publishing and account access",
};

export const ROLE_PERMISSIONS: Record<ApiRole, readonly string[]> = {
  citizen: [
    "Submit reports and review duplicate suggestions",
    "Attach their own report to another report in the same district",
    "View their reports and leave resolution feedback",
  ],
  partner: [
    "Review and respond to client reports in the organisation's districts",
    "View published challenges matched to their organisation",
    "Review match details and express interest",
  ],
  admin: [
    "View complaint queues and programme statistics",
    "Cluster reports into draft challenges, then rename and publish challenges",
    "Confirm or decline partner matches",
    "Create accounts and manage roles, organisations and account status",
  ],
};

export const CITIZEN_ONLY: readonly ApiRole[] = ["citizen"];
export const PARTNER_ONLY: readonly ApiRole[] = ["partner"];
// The staff queue is the partner workspace; administrators have their own
// console (`/admin`), so the two dashboards never overlap.
export const STAFF_PORTAL_ROLES: readonly ApiRole[] = ["partner"];
export const ADMIN_ONLY: readonly ApiRole[] = ["admin"];

export function can(
  role: ApiRole | null | undefined,
  capability: Capability,
): boolean {
  return role ? CAPABILITIES[role].includes(capability) : false;
}

/** The page a signed-in account lands on from the header. */
export function accountHome(role: ApiRole): string {
  if (role === "admin") return "/admin";
  if (role === "partner") return "/staff/dashboard";
  return "/reports";
}
