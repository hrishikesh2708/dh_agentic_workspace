"use client";

import { Card, CardContent } from "@/components/ui/card";
import type { MappingField } from "@/hooks/use-headless-interrupt";
import type { MappingCompleteMessage } from "@/lib/parse-agent-message";

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 90
      ? "bg-green-500/15 text-green-700 dark:text-green-400"
      : pct >= 50
        ? "bg-amber-500/15 text-amber-700 dark:text-amber-400"
        : "bg-red-500/15 text-red-700 dark:text-red-400";
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${color}`}>
      {pct}%
    </span>
  );
}

function formatStatus(status?: string): string {
  return (status ?? "unknown").replace(/_/g, " ");
}

export function MappingResultCard({ data }: { data: MappingCompleteMessage }) {
  const mappings: MappingField[] = data.mappings ?? [];
  const { total, auto_approved, human_reviewed } = data.stats;

  const routeLabel =
    data.mapping_kind === "projection"
      ? `${data.source_object} → ${data.destination_label}`
      : `${data.source_object} → Canonical`;

  return (
    <Card className="border-emerald-500/40 bg-emerald-500/5 w-full max-w-2xl">
      <CardContent className="p-4 space-y-4">
        <div>
          <p className="text-sm font-semibold text-[var(--foreground)]">{data.summary}</p>
          <p className="text-xs text-[var(--muted-foreground)] mt-1">
            <span className="font-medium">{routeLabel}</span>
            {" · via "}
            <span className="font-medium">{data.source_label}</span>
          </p>
        </div>

        <p className="text-xs text-[var(--muted-foreground)]">
          {total} field{total !== 1 ? "s" : ""} mapped
          {auto_approved > 0 && ` · ${auto_approved} auto-approved`}
          {human_reviewed > 0 && ` · ${human_reviewed} reviewed by you`}
        </p>

        <div className="rounded-md border border-[var(--border)] overflow-hidden text-xs max-h-80 overflow-y-auto">
          <table className="w-full">
            <thead className="sticky top-0 z-10">
              <tr className="bg-[var(--secondary)] border-b border-[var(--border)]">
                <th className="text-left px-3 py-2 font-medium text-[var(--muted-foreground)]">Source</th>
                <th className="text-left px-3 py-2 font-medium text-[var(--muted-foreground)]">Destination</th>
                <th className="text-left px-3 py-2 font-medium text-[var(--muted-foreground)]">Confidence</th>
                <th className="text-left px-3 py-2 font-medium text-[var(--muted-foreground)]">Status</th>
              </tr>
            </thead>
            <tbody>
              {mappings.map((m) => (
                <tr
                  key={m.source_field}
                  className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--secondary)]/50"
                >
                  <td className="px-3 py-2 font-mono text-[var(--foreground)]">{m.source_field}</td>
                  <td className="px-3 py-2 font-mono text-[var(--foreground)]">
                    {m.destination_field ?? "—"}
                  </td>
                  <td className="px-3 py-2">
                    <ConfidenceBadge value={m.confidence} />
                  </td>
                  <td className="px-3 py-2 capitalize text-[var(--muted-foreground)]">
                    {formatStatus(m.status)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
