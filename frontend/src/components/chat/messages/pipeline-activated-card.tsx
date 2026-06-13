"use client";

import { Card, CardContent } from "@/components/ui/card";
import type { PipelineActivatedMessage } from "@/lib/parse-agent-message";

export function PipelineActivatedCard({ data }: { data: PipelineActivatedMessage }) {
  return (
    <Card className="w-full max-w-lg border-[var(--border)] bg-[var(--card)] shadow-sm overflow-hidden">
      <div className="flex">
        {/* Green left accent bar */}
        <div className="w-1 shrink-0 bg-green-500" />

        <CardContent className="p-4 space-y-2 flex-1">
          {/* Title row */}
          <div className="flex items-center gap-2">
            <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-green-600 text-[9px] font-bold text-white leading-none">
              ✓
            </span>
            <p className="text-sm font-semibold text-[var(--foreground)]">Pipeline activated</p>
          </div>

          {/* Pipeline name */}
          {data.pipeline_name && (
            <p className="text-xs text-[var(--muted-foreground)] font-medium">{data.pipeline_name}</p>
          )}

          {/* Route */}
          <div className="flex items-center gap-1.5 flex-wrap text-sm text-[var(--foreground)]">
            <span className="font-medium">{data.source_label} · {data.source_object}</span>
            <span className="text-[var(--muted-foreground)]">→</span>
            <span className="font-medium">{data.destinations.join(", ")}</span>
          </div>

          {/* Stats */}
          <p className="text-xs text-[var(--muted-foreground)]">
            {data.mapped_fields} of {data.total_fields} fields mapped · live
          </p>
        </CardContent>
      </div>
    </Card>
  );
}
