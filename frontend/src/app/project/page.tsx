import { ProjectSelector } from "@/components/project/project-selector";

export default function ProjectPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--background)] p-4">
      <ProjectSelector />
    </div>
  );
}
