"use client";

import { Card, CardContent } from "@/components/ui/card";
import type { MappingField } from "@/hooks/use-headless-interrupt";
import type { MappingCompleteMessage } from "@/lib/parse-agent-message";

export function MappingResultCard({ data }: { data: MappingCompleteMessage }) {
  const mappings: MappingField[] = data.mappings ?? [];
  const { total, auto_approved, human_reviewed } = data.stats;

  const routeLabel =
    data.mapping_kind === "projection"
      ? `${data.source_label} ${data.source_object} → ${data.destination_label}`
      : `${data.source_label} ${data.source_object} → Canonical`;

  return (
    <Card className="w-full max-w-lg border-[var(--border)] bg-[var(--card)] shadow-sm">
      <CardContent className="p-4 space-y-3">
        {/* Header */}
        <div>
          <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
            {routeLabel}
          </p>
          <p className="text-xs text-[var(--muted-foreground)] mt-1">
            {total} fields mapped
            {auto_approved > 0 && ` · ${auto_approved} auto-approved`}
            {human_reviewed > 0 && ` · ${human_reviewed} reviewed by you`}
          </p>
        </div>

        {/* Mapping rows */}
        <div className="space-y-2">
          {mappings.map((m) => (
            <div key={m.source_field} className="flex items-center gap-2">
              {/* Source pill */}
              <div className="flex-1 min-w-0 rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 text-sm text-[var(--foreground)] truncate">
                {m.source_field}
              </div>

              {/* Arrow */}
              <span className="shrink-0 text-[var(--muted-foreground)] text-sm">→</span>

              {/* Destination pill */}
              <div className="flex-1 min-w-0 rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 text-sm text-[var(--foreground)] truncate">
                {m.destination_field ?? "—"}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
