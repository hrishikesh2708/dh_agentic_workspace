"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { SidebarUserFooter } from "./sidebar-user-footer";
import { useShell } from "./shell-context";

const NAV = [
  { href: "/chat", label: "Copilot" },
] as const;

export function ChatSidebar() {
  const pathname = usePathname();
  const { sidebarCollapsed, toggleSidebar } = useShell();

  return (
    <aside
      className={cn(
        "hidden h-screen shrink-0 flex-col border-r border-[var(--border)] bg-[var(--card)] transition-[width] duration-200 md:flex",
        sidebarCollapsed ? "w-14" : "w-52",
      )}
    >
      <div
        className={cn(
          "flex h-14 items-center border-b border-[var(--border)]",
          sidebarCollapsed ? "justify-center px-2" : "justify-between px-4",
        )}
      >
        {!sidebarCollapsed ? (
          <Link href="/chat" className="min-w-0">
            <div className="font-semibold leading-tight">Datahash</div>
            <div className="text-xs text-[var(--muted-foreground)]">
              agentic workspace
            </div>
          </Link>
        ) : (
          <Link href="/chat" className="font-semibold" title="Datahash">
            DH
          </Link>
        )}
        {!sidebarCollapsed && (
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            aria-label="Collapse sidebar"
            className="h-8 w-8 shrink-0"
          >
            ‹
          </Button>
        )}
      </div>

      {sidebarCollapsed && (
        <div className="flex justify-center py-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            aria-label="Expand sidebar"
            className="h-8 w-8"
          >
            ›
          </Button>
        </div>
      )}

      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 py-2">
        {NAV.map((item) => {
          const active =
            pathname === item.href || pathname.startsWith(`${item.href}/`);

          return (
            <Link
              key={item.href}
              href={item.href}
              title={sidebarCollapsed ? item.label : undefined}
              className={cn(
                "rounded-[var(--radius)] px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-[var(--secondary)] font-medium text-[var(--secondary-foreground)]"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--secondary-foreground)]",
                sidebarCollapsed && "flex justify-center px-2",
              )}
            >
              {sidebarCollapsed ? item.label.charAt(0) : item.label}
            </Link>
          );
        })}
      </nav>

      <SidebarUserFooter collapsed={sidebarCollapsed} />
    </aside>
  );
}
