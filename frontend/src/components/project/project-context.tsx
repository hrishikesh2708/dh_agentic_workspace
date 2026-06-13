"use client";

import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { ProjectRead } from "@/lib/types";

interface ProjectContextValue {
  project: ProjectRead;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({
  project,
  children,
}: {
  project: ProjectRead;
  children: ReactNode;
}) {
  const [current] = useState<ProjectRead>(project);
  const value = useMemo(() => ({ project: current }), [current]);
  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProject must be used within ProjectProvider");
  return ctx;
}
