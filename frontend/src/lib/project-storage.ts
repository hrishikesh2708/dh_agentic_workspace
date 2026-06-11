import type { ProjectRead } from "@/lib/types";

const ACTIVE_PROJECT_STORAGE_KEY = "dh_active_project";

export function isValidStoredProject(value: unknown): value is ProjectRead {
  if (!value || typeof value !== "object") return false;
  const project = value as ProjectRead;
  return (
    typeof project.id === "string" &&
    project.id.length > 0 &&
    typeof project.name === "string" &&
    project.name.trim().length > 0
  );
}

export function loadStoredProject(): ProjectRead | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!isValidStoredProject(parsed)) {
      window.sessionStorage.removeItem(ACTIVE_PROJECT_STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    window.sessionStorage.removeItem(ACTIVE_PROJECT_STORAGE_KEY);
    return null;
  }
}

export function storeProject(project: ProjectRead) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, JSON.stringify(project));
}

export function clearStoredProject() {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(ACTIVE_PROJECT_STORAGE_KEY);
}
