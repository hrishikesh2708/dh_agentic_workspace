"use client";

import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/use-theme";

const ORDER = ["light", "dark", "system"] as const;

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { theme, setTheme } = useTheme();

  function cycle() {
    const idx = ORDER.indexOf(theme as (typeof ORDER)[number]);
    const next = ORDER[(idx + 1) % ORDER.length];
    setTheme(next);
  }

  const label = theme === "light" ? "Light" : theme === "dark" ? "Dark" : "System";

  return (
    <Button
      variant="ghost"
      size={compact ? "icon" : "sm"}
      onClick={cycle}
      aria-label={`Theme: ${label}`}
      title={compact ? `Theme: ${label}` : undefined}
      className={compact ? "h-8 w-8" : undefined}
    >
      {compact ? (theme === "light" ? "☀" : theme === "dark" ? "☾" : "◐") : label}
    </Button>
  );
}
