import type { Metadata } from "next";
import "./globals.css";
import { LocaleProvider } from "@/components/locale-provider";
import { SessionProvider } from "@/components/session-provider";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

export const metadata: Metadata = {
  title: "ChallengeMap — Jharkhand's societal challenges, mapped",
  description:
    "ChallengeMap groups similar citizen complaints into ranked challenge briefs and matches them to universities, labs, NGOs and industry partners across Jharkhand.",
};

/**
 * Runs before first paint and before React hydrates:
 * - applies the stored (or system) theme so dark mode does not flash light
 *   then dark;
 * - strips `fdprocessedid`, a marker that Edge's form fill and some password
 *   manager extensions inject into every button/input/select. React then sees
 *   attributes it did not render and reports a hydration mismatch that cannot
 *   be patched. Extensions can add the marker after this script runs, hence the
 *   observer. Kept tiny and dependency-free on purpose.
 */
const headScript = `(function(){try{var stored=localStorage.getItem("challengemap.theme");var dark=stored?stored==="dark":window.matchMedia("(prefers-color-scheme: dark)").matches;if(dark){document.documentElement.classList.add("dark");}}catch(e){}var strip=function(){var nodes=document.querySelectorAll("[fdprocessedid]");for(var i=0;i<nodes.length;i++){nodes[i].removeAttribute("fdprocessedid");}};strip();try{new MutationObserver(strip).observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:["fdprocessedid"]});}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: headScript }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Sans+Devanagari:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-canvas text-fg antialiased">
        <LocaleProvider>
          <SessionProvider>
          <a
            href="#content"
            className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-lg focus:bg-ink focus:px-4 focus:py-2 focus:text-sm focus:text-white"
          >
            Skip to content
          </a>
          <SiteHeader />
          <main id="content">{children}</main>
          <SiteFooter />
          </SessionProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
