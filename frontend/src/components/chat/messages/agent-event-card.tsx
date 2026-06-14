"use client";

import { Card, CardContent } from "@/components/ui/card";
import type { AgentEventMessage } from "@/lib/parse-agent-message";

export function AgentEventCard({
  data,
  dimmed = false,
}: {
  data: AgentEventMessage;
  dimmed?: boolean;
}) {
  const isInProgress = data.status === "in_progress";

  return (
    <Card
      className={[
        "w-full max-w-lg transition-opacity",
        dimmed ? "opacity-50" : "",
        isInProgress
          ? "border-[var(--border)] bg-[var(--secondary)]/50"
          : "border-blue-500/30 bg-blue-500/5",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <CardContent className="p-4">
        {data.step_index !== undefined && data.step_total !== undefined && (
          <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wide mb-1">
            Step {data.step_index} of {data.step_total}
          </p>
        )}
        <p className="text-sm text-[var(--foreground)]">{data.message}</p>
      </CardContent>
    </Card>
  );
}
