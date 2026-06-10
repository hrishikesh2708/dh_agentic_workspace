"use client";

import type { AgentEventMessage } from "@/lib/parse-agent-message";

export function AgentEventLine({
  data,
  dimmed = false,
}: {
  data: AgentEventMessage;
  dimmed?: boolean;
}) {
  const isInProgress = data.status === "in_progress";

  return (
    <p
      className={[
        "max-w-[85%] text-sm",
        dimmed ? "opacity-50" : "",
        isInProgress
          ? "text-[var(--muted-foreground)] italic"
          : "text-[var(--foreground)]",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {data.message}
    </p>
  );
}
