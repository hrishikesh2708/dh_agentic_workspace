"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
}

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/mappings", label: "Mappings" },
  { href: "/golden-rules", label: "Golden Rules" },
  { href: "/integrations", label: "Integrations" },
  { href: "/chat", label: "Chat" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden h-screen w-60 shrink-0 border-r border-[var(--border)] bg-[var(--card)] md:flex md:flex-col">
      <div className="flex h-14 items-center px-6 font-semibold">
        <Link href="/dashboard">Datahash</Link>
      </div>
      <nav className="flex flex-col gap-1 px-3 py-2">
        {NAV.map((item) => {
          const active =
            pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "rounded-[var(--radius)] px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-[var(--secondary)] text-[var(--secondary-foreground)] font-medium"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--secondary-foreground)]",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
