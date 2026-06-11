"use client";

import { useEffect, useState } from "react";

import { apiClient, ApiError } from "@/lib/api-client";
import type { ProjectCreate, ProjectListResponse, ProjectRead } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Dropdown } from "@/components/ui/dropdown";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

type PickerMode = "existing" | "new";

interface ProjectPickerDialogProps {
  open: boolean;
  onComplete: (project: ProjectRead) => void;
}

export function ProjectPickerDialog({
  open,
  onComplete,
}: ProjectPickerDialogProps) {
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [mode, setMode] = useState<PickerMode>("new");
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [newProjectName, setNewProjectName] = useState("");

  const hasProjects = projects.length > 0;
  const activeMode: PickerMode = hasProjects ? mode : "new";

  useEffect(() => {
    if (!open) return;

    let cancelled = false;

    async function loadProjects() {
      setLoading(true);
      setError(null);
      try {
        const response = await apiClient.get<ProjectListResponse>("/projects");
        if (cancelled) return;
        setProjects(response.items);
        if (response.items.length === 0) {
          setMode("new");
          setSelectedProjectId("");
        } else {
          setMode("existing");
          setSelectedProjectId(response.items[0]?.id ?? "");
        }
      } catch (err) {
        if (cancelled) return;
        setProjects([]);
        setMode("new");
        setError(
          err instanceof ApiError ? err.message : "Could not load projects",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadProjects();
    return () => {
      cancelled = true;
    };
  }, [open]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      if (activeMode === "existing") {
        const selected = projects.find((p) => p.id === selectedProjectId);
        if (!selected) {
          setError("Select a project to continue");
          return;
        }
        onComplete(selected);
        return;
      }

      const trimmedName = newProjectName.trim();
      if (!trimmedName) {
        setError("Enter a project name");
        return;
      }

      const body: ProjectCreate = { name: trimmedName };
      const created = await apiClient.post<ProjectRead>("/projects", body);
      onComplete(created);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save project");
    } finally {
      setSubmitting(false);
    }
  }

  const title = hasProjects ? "Choose a project" : "Create your first project";
  const description = hasProjects
    ? "Copilot loads connections, mappings, and integrations from the active project."
    : "Name your workspace (e.g. Acme Production). You can create more projects later.";

  return (
    <Dialog open={open} dismissible={false}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-[var(--muted-foreground)]">
            <Spinner size="sm" />
            Loading your projects…
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {error ? (
              <div className="rounded-[var(--radius)] border border-[var(--destructive)] bg-[var(--destructive)]/10 px-3 py-2 text-sm text-[var(--destructive)]">
                {error}
              </div>
            ) : null}

            {hasProjects ? (
              <div className="grid gap-2 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setMode("existing")}
                  className={cn(
                    "rounded-[var(--radius)] border px-4 py-3 text-left text-sm transition-colors",
                    activeMode === "existing"
                      ? "border-[var(--primary)] bg-[var(--primary)]/5"
                      : "border-[var(--border)] hover:bg-[var(--secondary)]/40",
                  )}
                >
                  <p className="font-medium text-[var(--foreground)]">
                    Use existing project
                  </p>
                  <p className="mt-1 text-[var(--muted-foreground)]">
                    Resume where you left off.
                  </p>
                </button>
                <button
                  type="button"
                  onClick={() => setMode("new")}
                  className={cn(
                    "rounded-[var(--radius)] border px-4 py-3 text-left text-sm transition-colors",
                    activeMode === "new"
                      ? "border-[var(--primary)] bg-[var(--primary)]/5"
                      : "border-[var(--border)] hover:bg-[var(--secondary)]/40",
                  )}
                >
                  <p className="font-medium text-[var(--foreground)]">
                    Create new project
                  </p>
                  <p className="mt-1 text-[var(--muted-foreground)]">
                    Start a separate workspace.
                  </p>
                </button>
              </div>
            ) : null}

            {activeMode === "existing" ? (
              <div className="space-y-2">
                <Label htmlFor="project_id">Project</Label>
                <Dropdown
                  id="project_id"
                  value={selectedProjectId}
                  onChange={(e) => setSelectedProjectId(e.target.value)}
                  required
                >
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </Dropdown>
              </div>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="project_name">Project name</Label>
                <Input
                  id="project_name"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  placeholder="Acme Production"
                  required
                  autoFocus
                />
              </div>
            )}

            <DialogFooter>
              <Button type="submit" disabled={submitting || loading}>
                {submitting ? <Spinner size="sm" /> : null}
                {submitting
                  ? "Saving…"
                  : activeMode === "existing"
                    ? "Continue"
                    : "Create project"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
