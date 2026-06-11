"use client";

import { useRouter } from "next/navigation";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";

export function SidebarUserFooter({ collapsed }: { collapsed: boolean }) {
  const router = useRouter();
  const { user, loading, logout } = useAuth();

  const displayName = user?.email ?? user?.user_id + " " + "Signed in";

  async function onLogout() {
    await logout();
    router.replace("/login");
  }

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-2 border-t border-[var(--border)] px-2 py-3">
        <span
          title={displayName}
          className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--secondary)] text-xs font-medium text-[var(--secondary-foreground)]"
        >
          {loading ? "…" : displayName.charAt(0).toUpperCase()}
        </span>
        <ThemeToggle compact />
        <Button
          variant="ghost"
          size="icon"
          onClick={onLogout}
          aria-label="Sign out"
          className="h-8 w-8"
          title="Sign out"
        >
          ⎋
        </Button>
      </div>
    );
  }

  return (
    <div className="border-t border-[var(--border)] px-3 py-3">
      <div className="mb-3 min-w-0">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
            <Spinner size="sm" />
            Loading…
          </div>
        ) : (
          <>
            <p className="truncate text-sm font-medium text-[var(--foreground)]">
              {displayName}
            </p>
            {user?.email && user.user_id ? (
              <p className="truncate text-xs text-[var(--muted-foreground)]">
                {user.user_id}
              </p>
            ) : null}
          </>
        )}
      </div>
      <div className={cn("flex items-center gap-2")}>
        <ThemeToggle />
        <Button variant="outline" size="sm" onClick={onLogout} className="flex-1">
          Sign out
        </Button>
      </div>
    </div>
  );
}
