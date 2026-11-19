import Link from "next/link";
import { MapPinned, ShieldCheck } from "lucide-react";

export function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-line bg-ink text-white">
      <div className="shell grid gap-10 py-14 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-surface/10 text-teal-bright">
              <MapPinned className="h-5 w-5" aria-hidden />
            </span>
            <span className="text-[15px] font-extrabold tracking-tight">ChallengeMap</span>
          </div>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-white/60">
            Turning scattered citizen complaints into ranked, verifiable challenge briefs that
            universities, NGOs and industry can act on.
          </p>
          <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-white/15 px-3 py-1.5 text-xs text-white/70">
            <ShieldCheck className="h-3.5 w-3.5 text-teal-bright" aria-hidden />
            Demo data is synthetic, not a Jharkhand survey
          </div>
        </div>

        <FooterColumn
          title="Product"
          links={[
            { href: "/challenges", label: "Browse challenges" },
            { href: "/submit", label: "Report an issue" },
            { href: "/partners", label: "Partner directory" },
            { href: "/admin", label: "Admin console" },
          ]}
        />
        <FooterColumn
          title="Project"
          links={[
            { href: "/methodology", label: "Methodology" },
            { href: "/methodology#data", label: "Data provenance" },
            { href: "/methodology#metrics", label: "Evaluation metrics" },
            { href: "/methodology#limits", label: "Limitations" },
          ]}
        />
        <FooterColumn
          title="Account"
          links={[
            { href: "/login", label: "Sign in" },
            { href: "/register", label: "Create account" },
            { href: "/methodology#ethics", label: "Ethics & PII" },
          ]}
        />
      </div>
      <div className="border-t border-white/10">
        <div className="shell flex flex-wrap items-center justify-between gap-3 py-5 text-xs text-white/45">
          <p>ChallengeMap · Jharkhand societal challenge discovery · academic project</p>
          <p>
            State outline derived from OpenStreetMap relation 1960191 (ODbL 1.0) · built with
            Next.js and FastAPI
          </p>
        </div>
      </div>
    </footer>
  );
}

function FooterColumn({
  title,
  links,
}: {
  title: string;
  links: { href: string; label: string }[];
}) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-white/40">{title}</p>
      <ul className="mt-4 space-y-2.5">
        {links.map((link) => (
          <li key={link.href + link.label}>
            <Link
              href={link.href}
              className="text-sm text-white/70 transition-colors hover:text-white"
            >
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
