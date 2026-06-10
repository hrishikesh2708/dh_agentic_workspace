import { GoldenRulesTable } from "@/components/golden-rules/golden-rules-table";

export default function GoldenRulesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Golden rules</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Mapping patterns learned and confirmed across runs.
        </p>
      </div>
      <GoldenRulesTable />
    </div>
  );
}
