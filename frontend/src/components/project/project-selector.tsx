"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiClient, ApiError } from "@/lib/api-client";
import { storeProject } from "@/lib/project-storage";
import type { ProjectCreate, ProjectListResponse, ProjectRead } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Dropdown } from "@/components/ui/dropdown";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

type Mode = "existing" | "new";

export function ProjectSelector() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [mode, setMode] = useState<Mode>("new");
  const [selectedId, setSelectedId] = useState("");
  const [newName, setNewName] = useState("");

  const hasProjects = projects.length > 0;
  const activeMode: Mode = hasProjects ? mode : "new";

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await apiClient.get<ProjectListResponse>("/projects");
        if (cancelled) return;
        setProjects(res.items);
        if (res.items.length > 0) {
          setMode("existing");
          setSelectedId(res.items[0]?.id ?? "");
        } else {
          setMode("new");
        }
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Could not load projects");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => { cancelled = true; };
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      let project: ProjectRead;

      if (activeMode === "existing") {
        const found = projects.find((p) => p.id === selectedId);
        if (!found) { setError("Select a project to continue"); return; }
        project = found;
      } else {
        const trimmed = newName.trim();
        if (!trimmed) { setError("Enter a project name"); return; }
        const body: ProjectCreate = { name: trimmed };
        project = await apiClient.post<ProjectRead>("/projects", body);
      }

      storeProject(project); // sets sessionStorage + dh_project_id cookie
      router.push("/chat");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save project");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-md rounded-[var(--radius)] border border-[var(--border)] bg-[var(--card)] p-8 shadow-sm">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[var(--foreground)]">
          {hasProjects ? "Choose a project" : "Create your first project"}
        </h1>
        <p className="mt-1 text-sm text-[var(--muted-foreground)]">
          {hasProjects
            ? "Select a workspace to continue to Copilot."
            : "Name your workspace (e.g. Acme Production). You can create more later."}
        </p>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-4 text-sm text-[var(--muted-foreground)]">
          <Spinner size="sm" /> Loading your projects…
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="rounded-[var(--radius)] border border-[var(--destructive)] bg-[var(--destructive)]/10 px-3 py-2 text-sm text-[var(--destructive)]">
              {error}
            </div>
          )}

          {hasProjects && (
            <div className="grid gap-2 sm:grid-cols-2">
              {(["existing", "new"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={cn(
                    "rounded-[var(--radius)] border px-4 py-3 text-left text-sm transition-colors",
                    activeMode === m
                      ? "border-[var(--primary)] bg-[var(--primary)]/5"
                      : "border-[var(--border)] hover:bg-[var(--secondary)]/40",
                  )}
                >
                  <p className="font-medium text-[var(--foreground)]">
                    {m === "existing" ? "Use existing" : "Create new"}
                  </p>
                  <p className="mt-0.5 text-[var(--muted-foreground)]">
                    {m === "existing" ? "Resume where you left off." : "Start a new workspace."}
                  </p>
                </button>
              ))}
            </div>
          )}

          {activeMode === "existing" ? (
            <div className="space-y-2">
              <Label htmlFor="project_id">Project</Label>
              <Dropdown
                id="project_id"
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                required
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </Dropdown>
            </div>
          ) : (
            <div className="space-y-2">
              <Label htmlFor="project_name">Project name</Label>
              <Input
                id="project_name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Acme Production"
                required
                autoFocus
              />
            </div>
          )}

          <Button type="submit" className="w-full" disabled={submitting || loading}>
            {submitting && <Spinner size="sm" />}
            {submitting ? "Saving…" : activeMode === "existing" ? "Continue" : "Create project"}
          </Button>
        </form>
      )}
    </div>
  );
}
