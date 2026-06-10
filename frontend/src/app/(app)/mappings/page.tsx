import { MappingsTable } from "@/components/mappings/mappings-table";

export default function MappingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Mappings</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Every mapping run executed against your account.
        </p>
      </div>
      <MappingsTable />
    </div>
  );
}
