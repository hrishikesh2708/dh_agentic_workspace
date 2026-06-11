"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { MOCK_PIPELINES } from "@/lib/mock-workspace";

interface ShellContextValue {
  sidebarCollapsed: boolean;
  rightPanelCollapsed: boolean;
  selectedPipelineId: string;
  toggleSidebar: () => void;
  toggleRightPanel: () => void;
  setSelectedPipelineId: (id: string) => void;
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
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);
  const [selectedPipelineId, setSelectedPipelineId] = useState(
    MOCK_PIPELINES[0]?.id ?? "",
  );

  const toggleSidebar = useCallback(
    () => setSidebarCollapsed((prev) => !prev),
    [],
  );
  const toggleRightPanel = useCallback(
    () => setRightPanelCollapsed((prev) => !prev),
    [],
  );

  const value = useMemo(
    () => ({
      sidebarCollapsed,
      rightPanelCollapsed,
      selectedPipelineId,
      toggleSidebar,
      toggleRightPanel,
      setSelectedPipelineId,
    }),
    [
      sidebarCollapsed,
      rightPanelCollapsed,
      selectedPipelineId,
      toggleSidebar,
      toggleRightPanel,
    ],
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
