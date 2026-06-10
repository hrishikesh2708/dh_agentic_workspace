"use client";

import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { useAuth } from "@/hooks/use-auth";

export function Topbar() {
  const router = useRouter();
  const { user, logout } = useAuth();

  async function onLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <header className="flex h-14 items-center justify-between border-b border-[var(--border)] bg-[var(--background)] px-6">
      <div className="text-sm text-[var(--muted-foreground)]">
        {user?.email ?? user?.user_id ?? ""}
      </div>
      <div className="flex items-center gap-2">
        <ThemeToggle />
        <Button variant="outline" size="sm" onClick={onLogout}>
          Sign out
        </Button>
      </div>
    </header>
  );
}
