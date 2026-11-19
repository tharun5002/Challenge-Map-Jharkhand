"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { LogOut, MapPinned, Menu, Plus, UserRound, X } from "lucide-react";
import { useI18n } from "@/components/locale-provider";
import { useSession } from "@/components/session-provider";
import { ThemeToggle } from "@/components/theme-toggle";
import { LOCALES, type MessageKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { ROLE_LABELS, accountHome, can } from "@/lib/roles";

const NAV: { href: string; key: MessageKey }[] = [
  { href: "/challenges", key: "nav.challenges" },
  { href: "/partners", key: "nav.partners" },
  { href: "/staff/dashboard", key: "nav.partnerPortal" },
  { href: "/reports", key: "nav.reports" },
  { href: "/admin", key: "nav.admin" },
  { href: "/methodology", key: "nav.methodology" },
];

function LocaleSwitcher({ className }: { className?: string }) {
  const { locale, setLocale, t } = useI18n();
  return (
    <div
      role="group"
      aria-label={t("locale.label")}
      className={cn(
        "flex items-center gap-0.5 rounded-lg border border-line bg-surface p-0.5",
        className,
      )}
    >
      {LOCALES.map((item) => (
        <button
          key={item.code}
          type="button"
          onClick={() => setLocale(item.code)}
          aria-pressed={locale === item.code}
          lang={item.htmlLang}
          className={cn(
            "rounded-md px-2 py-1 text-[11px] font-semibold transition",
            locale === item.code
              ? "bg-teal text-white"
              : "text-fg-muted hover:text-fg",
          )}
        >
          {item.short}
        </button>
      ))}
    </div>
  );
}

export function SiteHeader() {
  const pathname = usePathname();
  const { t } = useI18n();
  const { user, ready, signOut } = useSession();
  const [open, setOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const accountMenuRef = useRef<HTMLDivElement>(null);
  const accountButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!accountOpen) return;

    function handlePointerDown(event: PointerEvent) {
      if (
        event.target instanceof Node &&
        !accountMenuRef.current?.contains(event.target)
      ) {
        setAccountOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setAccountOpen(false);
        accountButtonRef.current?.focus();
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [accountOpen]);

  // Role-bound destinations are only advertised to the role that can use them;
  // the API rejects everyone else regardless of what the header shows.
  const navItems = NAV.filter((item) => {
    if (item.href === "/admin") return can(user?.role, "admin:console");
    if (item.href === "/staff/dashboard") {
      return can(user?.role, "partner:matches");
    }
    if (item.href === "/reports") return can(user?.role, "complaints:feedback");
    return true;
  });
  // Filing a report is a citizen action; anonymous visitors are sent to sign in.
  const canReport = !user || can(user.role, "complaints:submit");
  const mobileItems = canReport
    ? navItems.concat([{ href: "/submit", key: "nav.report" as MessageKey }])
    : navItems;

  return (
    <header className="sticky top-0 z-50 border-b border-line bg-canvas/85 backdrop-blur-md">
      <div className="flex h-16 w-full items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-2.5" aria-label={t("nav.home")}>
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-ink text-teal-bright">
            <MapPinned className="h-5 w-5" aria-hidden />
          </span>
          <span className="text-[15px] font-extrabold tracking-tight">
            Challenge<span className="text-teal">Map</span>
            <span className="ml-2 hidden rounded-md border border-line px-1.5 py-0.5 align-middle text-[10px] font-semibold uppercase tracking-wider text-fg-subtle sm:inline">
              {t("brand.tag")}
            </span>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          {navItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active ? "bg-fg/5 text-fg" : "text-fg-soft hover:bg-fg/5 hover:text-fg",
                )}
              >
                {t(item.key)}
              </Link>
            );
          })}
        </nav>

        <div className="flex shrink-0 items-center gap-2">
          <LocaleSwitcher className="hidden sm:flex" />
          <ThemeToggle />
          {ready && user ? (
            <div className="relative" ref={accountMenuRef}>
              <button
                ref={accountButtonRef}
                type="button"
                aria-expanded={accountOpen}
                aria-controls="account-menu"
                aria-label={t("auth.accountMenu")}
                title={t("auth.accountMenu")}
                onClick={() => setAccountOpen((value) => !value)}
                className="grid h-10 w-10 place-items-center rounded-full border border-line-strong bg-surface text-fg-soft transition hover:border-teal hover:text-teal"
              >
                <UserRound className="h-[18px] w-[18px]" aria-hidden />
              </button>
              {accountOpen ? (
                <div
                  id="account-menu"
                  className="absolute right-0 top-full z-50 mt-2 w-60 overflow-hidden rounded-xl border border-line bg-surface p-1.5 shadow-card"
                >
                  <div className="border-b border-line px-3 py-2.5">
                    <p className="truncate text-sm font-semibold text-fg">
                      {user.full_name || user.username}
                    </p>
                    <p className="mt-0.5 text-xs text-fg-muted">
                      {ROLE_LABELS[user.role]}
                    </p>
                  </div>
                  <Link
                    href={accountHome(user.role)}
                    onClick={() => setAccountOpen(false)}
                    className="mt-1 block rounded-lg px-3 py-2 text-sm font-medium text-fg-soft transition hover:bg-fg/5 hover:text-fg"
                  >
                    {t("nav.accountHome")}
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      signOut();
                      setAccountOpen(false);
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium text-fg-soft transition hover:bg-crimson/5 hover:text-crimson"
                  >
                    <LogOut className="h-4 w-4" aria-hidden />
                    {t("auth.signOut")}
                  </button>
                </div>
              ) : null}
            </div>
          ) : (
            <Link
              href="/login"
              className="rounded-lg px-2 py-2 text-sm font-semibold text-fg-soft transition hover:text-fg sm:px-3"
            >
              {t("nav.signIn")}
            </Link>
          )}
          {canReport ? (
            <Link
              href="/submit"
              className="hidden items-center gap-1.5 rounded-xl bg-teal px-3.5 py-2 text-sm font-semibold text-white transition hover:bg-teal-deep sm:inline-flex"
            >
              <Plus className="h-4 w-4" aria-hidden />
              {t("nav.report")}
            </Link>
          ) : null}
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            className="grid h-10 w-10 place-items-center rounded-lg border border-line text-fg md:hidden"
            aria-expanded={open}
            aria-label={open ? t("nav.closeMenu") : t("nav.openMenu")}
          >
            {open ? (
              <X className="h-5 w-5" aria-hidden />
            ) : (
              <Menu className="h-5 w-5" aria-hidden />
            )}
          </button>
        </div>
      </div>

      {open ? (
        <div className="border-t border-line bg-canvas md:hidden">
          <div className="shell flex flex-col gap-1 py-3">
            {mobileItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2.5 text-sm font-medium text-fg-strong hover:bg-fg/5"
              >
                {t(item.key)}
              </Link>
            ))}
            {!(ready && user) ? (
              <Link
                href="/login"
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2.5 text-sm font-medium text-fg-strong hover:bg-fg/5"
              >
                {t("nav.signIn")}
              </Link>
            ) : null}
            <div className="mt-2 flex items-center justify-between border-t border-line pt-3">
              <LocaleSwitcher />
              <ThemeToggle />
            </div>
          </div>
        </div>
      ) : null}
    </header>
  );
}
