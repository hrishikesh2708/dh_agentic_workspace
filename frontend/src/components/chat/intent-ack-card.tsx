"use client";

import { Card, CardContent } from "@/components/ui/card";
import type { IntentAckMessage } from "@/lib/parse-agent-message";

export function IntentAckCard({ data }: { data: IntentAckMessage }) {
  const chips: { label: string; value: string }[] = [];
  if (data.source_label) {
    chips.push({ label: "Source", value: data.source_label });
  }
  if (data.source_object) {
    chips.push({ label: "Object", value: data.source_object });
  }
  if (data.destination_label) {
    chips.push({ label: "Destination", value: data.destination_label });
  }

  return (
    <Card className="border-emerald-500/30 bg-emerald-500/5 w-full max-w-lg">
      <CardContent className="p-4 space-y-3">
        {data.complete && data.subtitle && (
          <p className="text-xs font-medium text-emerald-700 dark:text-emerald-400 uppercase tracking-wide">
            {data.subtitle}
          </p>
        )}
        <p className="text-sm text-[var(--foreground)]">{data.message}</p>
        {chips.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {chips.map((chip) => (
              <span
                key={chip.label}
                className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1 text-xs"
              >
                <span className="text-[var(--muted-foreground)]">{chip.label}</span>
                <span className="font-medium text-[var(--foreground)]">{chip.value}</span>
              </span>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
