import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

export function ShellLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen w-full bg-[var(--background)]">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Topbar />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
