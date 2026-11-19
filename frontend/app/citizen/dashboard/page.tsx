import { redirect } from "next/navigation";

/**
 * A citizen's dashboard is their report list, so the role-named URL resolves to
 * the one implementation instead of duplicating it.
 */
export default function CitizenDashboardPage() {
  redirect("/reports");
}
