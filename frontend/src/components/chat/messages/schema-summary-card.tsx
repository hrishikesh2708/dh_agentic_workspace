"use client";

import { Card, CardContent } from "@/components/ui/card";
import type { SchemaSummaryMessage } from "@/lib/parse-agent-message";

export function SchemaSummaryCard({ data }: { data: SchemaSummaryMessage }) {
  const shown = data.sample_fields?.slice(0, 6) ?? [];
  const overflow = (data.sample_fields?.length ?? 0) - shown.length;

  return (
    <Card className="w-full max-w-lg border-[var(--border)] bg-[var(--card)] shadow-sm">
      <CardContent className="p-4 space-y-3">
        {/* Header */}
        <div>
          <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
            Schema discovered
          </p>
          <p className="text-sm font-semibold text-[var(--foreground)] mt-1">
            {data.source_label} · {data.source_object}
          </p>
        </div>

        {/* Stats row */}
        <div className="flex gap-6">
          <div>
            <p className="text-2xl font-bold tabular-nums text-[var(--foreground)]">{data.total_fields}</p>
            <p className="text-[10px] uppercase tracking-wider font-medium text-[var(--muted-foreground)] mt-0.5">Total fields</p>
          </div>
          <div>
            <p className="text-2xl font-bold tabular-nums text-blue-600 dark:text-blue-400">{data.required_fields}</p>
            <p className="text-[10px] uppercase tracking-wider font-medium text-[var(--muted-foreground)] mt-0.5">Required</p>
          </div>
        </div>

        {/* Sample field chips */}
        {shown.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {shown.map((f) => (
              <span
                key={f}
                className="rounded-md border border-[var(--border)] bg-[var(--muted)] px-2 py-0.5 text-xs font-mono text-[var(--foreground)]"
              >
                {f}
              </span>
            ))}
            {overflow > 0 && (
              <span className="self-center text-xs text-[var(--muted-foreground)]">
                +{overflow} more
              </span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
