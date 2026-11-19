"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { useI18n } from "@/components/locale-provider";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "challengemap.theme";

/**
 * Class-based dark mode toggle. The theme is applied to <html> before paint by
 * the inline script in app/layout.tsx, so this only flips the current state.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { t } = useI18n();
  const [dark, setDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
    setMounted(true);
  }, []);

  function toggle() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    window.localStorage.setItem(STORAGE_KEY, next ? "dark" : "light");
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={dark ? t("theme.toLight") : t("theme.toDark")}
      aria-pressed={dark}
      title={dark ? t("theme.toLight") : t("theme.toDark")}
      className={cn(
        "grid h-9 w-9 place-items-center rounded-lg border border-line bg-surface text-fg-muted transition hover:text-fg",
        className,
      )}
    >
      {/* Render a stable icon until the stored theme is known, so SSR and the
          first client paint agree. */}
      {mounted && dark ? (
        <Sun className="h-4 w-4" aria-hidden />
      ) : (
        <Moon className="h-4 w-4" aria-hidden />
      )}
    </button>
  );
}
