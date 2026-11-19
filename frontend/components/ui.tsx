import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Severity } from "@/lib/types";

const severityTone: Record<Severity, string> = {
  critical: "bg-crimson/10 text-crimson border-crimson/20",
  high: "bg-amber/10 text-amber border-amber/25",
  medium: "bg-teal/10 text-teal border-teal/25",
  low: "bg-fg/5 text-fg-soft border-line-strong",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        severityTone[severity],
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {severity}
    </span>
  );
}

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: "neutral" | "teal" | "amber" | "crimson";
  className?: string;
}) {
  const tones = {
    neutral: "border-line bg-surface/70 text-fg-soft",
    teal: "border-teal/25 bg-teal/10 text-teal-deep",
    amber: "border-amber/25 bg-amber-soft text-amber",
    crimson: "border-crimson/20 bg-crimson/10 text-crimson",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function ButtonLink({
  href,
  children,
  variant = "primary",
  className,
}: {
  href: string;
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "inverse";
  className?: string;
}) {
  const variants = {
    primary:
      "bg-teal text-white hover:bg-teal-deep shadow-[0_10px_24px_-12px_rgba(15,118,110,0.9)]",
    secondary: "border border-line-strong bg-surface text-fg hover:border-line-strong hover:bg-surface-2",
    ghost: "text-fg-strong hover:bg-fg/5",
    inverse: "bg-surface text-fg hover:bg-surface-3",
  };
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors duration-150",
        variants[variant],
        className,
      )}
    >
      {children}
    </Link>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-4", className)}>
      <div className="max-w-2xl">
        {eyebrow ? <p className="eyebrow mb-2">{eyebrow}</p> : null}
        <h2 className="h2">{title}</h2>
        {description ? <p className="mt-3 text-fg-soft">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function Stat({
  value,
  label,
  note,
  tone = "light",
}: {
  value: string;
  label: string;
  note?: string;
  tone?: "light" | "dark";
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border p-5",
        tone === "light" ? "border-line bg-surface" : "border-white/10 bg-surface/5",
      )}
    >
      <p
        className={cn(
          "text-3xl font-extrabold tracking-tight",
          tone === "light" ? "text-fg" : "text-white",
        )}
      >
        {value}
      </p>
      <p
        className={cn(
          "mt-1 text-sm font-medium",
          tone === "light" ? "text-fg-strong" : "text-white/80",
        )}
      >
        {label}
      </p>
      {note ? (
        <p className={cn("mt-1 text-xs", tone === "light" ? "text-fg-subtle" : "text-white/50")}>
          {note}
        </p>
      ) : null}
    </div>
  );
}

export function ProgressBar({
  value,
  tone = "teal",
  className,
}: {
  value: number;
  tone?: "teal" | "amber" | "crimson";
  className?: string;
}) {
  const tones = { teal: "bg-teal", amber: "bg-amber", crimson: "bg-crimson" };
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <div
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-fg/10", className)}
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className={cn("h-full rounded-full", tones[tone])} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function PriorityPill({ score }: { score: number }) {
  const tone = score >= 80 ? "crimson" : score >= 70 ? "amber" : "teal";
  const label = score >= 80 ? "Urgent" : score >= 70 ? "High" : "Moderate";
  return (
    <Badge tone={tone}>
      <span className="font-bold">{score}</span>
      <span className="opacity-70">/100 {label}</span>
    </Badge>
  );
}

export function TextLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="inline-flex items-center gap-1.5 text-sm font-semibold text-teal transition hover:gap-2.5"
    >
      {children}
      <ArrowRight className="h-4 w-4" aria-hidden />
    </Link>
  );
}
