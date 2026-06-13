"use client";

import { Card, CardContent } from "@/components/ui/card";
import {
  formatAgentStepLabel,
  type AgentEventMessage,
} from "@/lib/parse-agent-message";

export function AgentEventCard({
  data,
  dimmed = false,
}: {
  data: AgentEventMessage;
  dimmed?: boolean;
}) {
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

  const stepLabel = formatAgentStepLabel(data);
  const isConfirmed = data.status === "confirmed";
  const isInProgress = data.status === "in_progress";

  return (
    <Card
      className={[
        "w-full max-w-lg transition-opacity",
        dimmed ? "opacity-50" : "",
        isConfirmed
          ? "border-emerald-500/30 bg-emerald-500/5"
          : isInProgress
            ? "border-[var(--border)] bg-[var(--secondary)]/50"
            : "border-blue-500/30 bg-blue-500/5",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <CardContent className="p-4 space-y-3">
        {stepLabel && (
          <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide flex items-center gap-1.5">
            {isConfirmed && (
              <span
                className="inline-flex size-3.5 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-[10px] font-bold leading-none text-white"
                aria-hidden
              >
                ✓
              </span>
            )}
            <span>
              {stepLabel}
              {isConfirmed ? " · confirmed" : isInProgress ? " · in progress" : ""}
            </span>
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
