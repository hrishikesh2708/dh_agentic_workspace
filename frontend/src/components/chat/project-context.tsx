"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  clearStoredProject,
  loadStoredProject,
  storeProject,
} from "@/lib/project-storage";
import type { ProjectRead } from "@/lib/types";

interface ProjectContextValue {
  project: ProjectRead;
  setProject: (project: ProjectRead) => void;
  clearProject: () => void;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({
  initialProject,
  children,
}: {
  initialProject: ProjectRead;
  children: ReactNode;
}) {
  const [project, setProjectState] = useState<ProjectRead>(initialProject);

  useEffect(() => {
    setProjectState(initialProject);
  }, [initialProject]);

  const setProject = useCallback((next: ProjectRead) => {
    storeProject(next);
    setProjectState(next);
  }, []);

  const clearProject = useCallback(() => {
    clearStoredProject();
    setProjectState(initialProject);
  }, [initialProject]);

  const value = useMemo(
    () => ({
      project,
      setProject,
      clearProject,
    }),
    [project, setProject, clearProject],
  );

  return (
    <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>
  );
}

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) {
    throw new Error("useProject must be used within ProjectProvider");
  }
  return ctx;
}

export function readInitialProject(): ProjectRead | null {
  return loadStoredProject();
}
