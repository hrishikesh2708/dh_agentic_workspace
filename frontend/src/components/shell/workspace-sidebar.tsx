"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  MOCK_CONNECTORS,
  MOCK_PIPELINES,
  type MockPipeline,
} from "@/lib/mock-workspace";
import { cn } from "@/lib/utils";

import { useShell } from "./shell-context";

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-3 pb-1 pt-3 text-xs font-medium uppercase tracking-wide text-[var(--muted-foreground)]">
      {children}
    </div>
  );
}

function PipelineItem({
  pipeline,
  active,
  collapsed,
  onSelect,
}: {
  pipeline: MockPipeline;
  active: boolean;
  collapsed: boolean;
  onSelect: () => void;
}) {
  const label = `${pipeline.source} → ${pipeline.destination}`;

  return (
    <button
      type="button"
      onClick={onSelect}
      title={collapsed ? label : undefined}
      className={cn(
        "flex w-full items-center gap-2 rounded-[var(--radius)] px-3 py-2 text-left text-sm transition-colors",
        active
          ? "bg-[var(--secondary)] font-medium text-[var(--secondary-foreground)]"
          : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--secondary-foreground)]",
        collapsed && "justify-center px-2",
      )}
    >
      <span
        className={cn(
          "flex h-5 w-5 shrink-0 items-center justify-center rounded border border-[var(--border)] text-[10px]",
          active && "border-[var(--foreground)]",
        )}
      >
        □
      </span>
      {!collapsed && (
        <>
          <span className="min-w-0 flex-1 truncate">{label}</span>
          {pipeline.status === "review" && (
            <Badge variant="warning" className="shrink-0">
              Review
            </Badge>
          )}
        </>
      )}
    </button>
  );
}

function NavLink({
  href,
  label,
  collapsed,
  badge,
}: {
  href: string;
  label: string;
  collapsed: boolean;
  badge?: React.ReactNode;
}) {
  const pathname = usePathname();
  const active = pathname === href || pathname.startsWith(`${href}/`);

  return (
    <Link
      href={href}
      title={collapsed ? label : undefined}
      className={cn(
        "flex items-center gap-2 rounded-[var(--radius)] px-3 py-2 text-sm transition-colors",
        active
          ? "bg-[var(--secondary)] font-medium text-[var(--secondary-foreground)]"
          : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--secondary-foreground)]",
        collapsed && "justify-center px-2",
      )}
    >
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded border border-[var(--border)] text-[10px]">
        □
      </span>
      {!collapsed && (
        <>
          <span className="min-w-0 flex-1 truncate">{label}</span>
          {badge}
        </>
      )}
    </Link>
  );
}

function ConnectorIcon({ name, icon }: { name: string; icon: string }) {
  return (
    <span
      title={name}
      className="flex h-8 w-8 items-center justify-center rounded-[var(--radius)] border border-[var(--border)] bg-[var(--background)] text-xs font-semibold"
    >
      {icon}
    </span>
  );
}

export function WorkspaceSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { sidebarCollapsed, toggleSidebar, selectedPipelineId, setSelectedPipelineId } =
    useShell();

  const authenticated = MOCK_CONNECTORS.filter((c) => c.authenticated);
  const onFutureDashboard =
    pathname === "/future-dashboard" ||
    pathname.startsWith("/future-dashboard/");

  return (
    <aside
      className={cn(
        "hidden h-screen shrink-0 flex-col border-r border-[var(--border)] bg-[var(--card)] transition-[width] duration-200 md:flex",
        sidebarCollapsed ? "w-14" : "w-60",
      )}
    >
      <div
        className={cn(
          "flex h-14 items-center border-b border-[var(--border)]",
          sidebarCollapsed ? "justify-center px-2" : "justify-between px-4",
        )}
      >
        {!sidebarCollapsed ? (
          <Link href="/future-dashboard" className="min-w-0">
            <div className="font-semibold leading-tight">Datahash</div>
            <div className="text-xs text-[var(--muted-foreground)]">
              agentic workspace
            </div>
          </Link>
        ) : (
          <Link href="/future-dashboard" className="font-semibold" title="Datahash">
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

      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 py-2">
        <SectionLabel>{sidebarCollapsed ? "·" : "Pipelines"}</SectionLabel>
        {MOCK_PIPELINES.map((pipeline) => (
          <PipelineItem
            key={pipeline.id}
            pipeline={pipeline}
            active={onFutureDashboard && selectedPipelineId === pipeline.id}
            collapsed={sidebarCollapsed}
            onSelect={() => {
              setSelectedPipelineId(pipeline.id);
              if (!onFutureDashboard) {
                router.push("/future-dashboard");
              }
            }}
          />
        ))}
        <button
          type="button"
          title={sidebarCollapsed ? "New pipeline" : undefined}
          className={cn(
            "flex w-full items-center gap-2 rounded-[var(--radius)] px-3 py-2 text-sm text-[var(--muted-foreground)] transition-colors hover:bg-[var(--secondary)] hover:text-[var(--secondary-foreground)]",
            sidebarCollapsed && "justify-center px-2",
          )}
        >
          <span className="text-base leading-none">+</span>
          {!sidebarCollapsed && <span>New pipeline</span>}
        </button>

        <SectionLabel>{sidebarCollapsed ? "·" : "Monitor"}</SectionLabel>
        <NavLink
          href="/future-dashboard"
          label="Health"
          collapsed={sidebarCollapsed}
          badge={
            !sidebarCollapsed ? (
              <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--destructive)] px-1.5 text-[10px] font-medium text-[var(--destructive-foreground)]">
                2
              </span>
            ) : undefined
          }
        />
        <button
          type="button"
          title={sidebarCollapsed ? "Signal report" : undefined}
          className={cn(
            "flex w-full items-center gap-2 rounded-[var(--radius)] px-3 py-2 text-sm text-[var(--muted-foreground)] transition-colors hover:bg-[var(--secondary)] hover:text-[var(--secondary-foreground)]",
            sidebarCollapsed && "justify-center px-2",
          )}
        >
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded border border-[var(--border)] text-[10px]">
            □
          </span>
          {!sidebarCollapsed && <span>Signal report</span>}
        </button>

        <SectionLabel>{sidebarCollapsed ? "·" : "Workspace"}</SectionLabel>
        {["GTM migrator", "Segments", "Settings"].map((item) => (
          <button
            key={item}
            type="button"
            title={sidebarCollapsed ? item : undefined}
            className={cn(
              "flex w-full items-center gap-2 rounded-[var(--radius)] px-3 py-2 text-sm text-[var(--muted-foreground)] transition-colors hover:bg-[var(--secondary)] hover:text-[var(--secondary-foreground)]",
              sidebarCollapsed && "justify-center px-2",
            )}
          >
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded border border-[var(--border)] text-[10px]">
              □
            </span>
            {!sidebarCollapsed && <span>{item}</span>}
          </button>
        ))}

        <SectionLabel>{sidebarCollapsed ? "·" : "Integrations"}</SectionLabel>
        <NavLink
          href="/integrations"
          label="All integrations"
          collapsed={sidebarCollapsed}
        />
        <div
          className={cn(
            "flex flex-wrap gap-2 px-3 py-1",
            sidebarCollapsed && "justify-center px-1",
          )}
        >
          {authenticated.length > 0 ? (
            authenticated.map((connector) => (
              <ConnectorIcon
                key={connector.id}
                name={connector.name}
                icon={connector.icon}
              />
            ))
          ) : (
            <Link
              href="/integrations"
              title="Add connector"
              className="flex h-8 w-8 items-center justify-center rounded-[var(--radius)] border border-dashed border-[var(--border)] text-[var(--muted-foreground)] transition-colors hover:bg-[var(--secondary)] hover:text-[var(--secondary-foreground)]"
            >
              +
            </Link>
          )}
        </div>

        <div className="mt-auto border-t border-[var(--border)] pt-2">
          <NavLink href="/chat" label="Back to Copilot" collapsed={sidebarCollapsed} />
        </div>
      </nav>
    </aside>
  );
}
