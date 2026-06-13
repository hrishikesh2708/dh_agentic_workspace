"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface ShellContextValue {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
}

const ShellContext = createContext<ShellContextValue | null>(null);

export function ShellProvider({
  children,
  defaultSidebarCollapsed = false,
}: {
  children: ReactNode;
  defaultSidebarCollapsed?: boolean;
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(defaultSidebarCollapsed);

  const toggleSidebar = useCallback(
    () => setSidebarCollapsed((prev) => !prev),
    [],
  );

  const value = useMemo(
    () => ({ sidebarCollapsed, toggleSidebar }),
    [sidebarCollapsed, toggleSidebar],
  );

  return (
    <ShellContext.Provider value={value}>{children}</ShellContext.Provider>
  );
}

export function useShell() {
  const ctx = useContext(ShellContext);
  if (!ctx) {
    throw new Error("useShell must be used within ShellProvider");
  }
  return ctx;
}
