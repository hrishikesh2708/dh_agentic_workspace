"use client";

import { ChatSidebar } from "./chat-sidebar";
import { ShellProvider } from "./shell-context";

export function ShellLayout({ children }: { children: React.ReactNode }) {
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
