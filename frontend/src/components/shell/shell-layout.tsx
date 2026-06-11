"use client";

import { usePathname } from "next/navigation";

import { ChatSidebar } from "./chat-sidebar";
import { RightPanel } from "./right-panel";
import { ShellProvider } from "./shell-context";
import { Topbar } from "./topbar";
import { WorkspaceSidebar } from "./workspace-sidebar";

function isFutureDashboardRoute(pathname: string) {
  return (
    pathname === "/future-dashboard" ||
    pathname.startsWith("/future-dashboard/")
  );
}

function isChatRoute(pathname: string) {
  return pathname === "/chat" || pathname.startsWith("/chat/");
}

export function ShellLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const futureDashboard = isFutureDashboardRoute(pathname);
  const chatRoute = isChatRoute(pathname);

  if (chatRoute) {
    return (
      <ShellProvider defaultSidebarCollapsed>
        <div className="flex h-screen w-full bg-[var(--background)]">
          <ChatSidebar />
          <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
            {children}
          </main>
        </div>
      </ShellProvider>
    );
  }

  if (futureDashboard) {
    return (
      <ShellProvider>
        <div className="flex h-screen w-full bg-[var(--background)]">
          <WorkspaceSidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <Topbar />
            <main className="flex-1 overflow-auto p-6">{children}</main>
          </div>
          <RightPanel />
        </div>
      </ShellProvider>
    );
  }

  return (
    <ShellProvider defaultSidebarCollapsed>
      <div className="flex h-screen w-full bg-[var(--background)]">
        <ChatSidebar />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </ShellProvider>
  );
}
