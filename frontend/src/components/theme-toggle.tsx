"use client";

import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/use-theme";

const ORDER = ["light", "dark", "system"] as const;

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  function cycle() {
    const idx = ORDER.indexOf(theme as (typeof ORDER)[number]);
    const next = ORDER[(idx + 1) % ORDER.length];
    setTheme(next);
  }

  return (
    <Button variant="ghost" size="sm" onClick={cycle} aria-label="Toggle theme">
      {theme === "light" ? "Light" : theme === "dark" ? "Dark" : "System"}
    </Button>
  );
}
