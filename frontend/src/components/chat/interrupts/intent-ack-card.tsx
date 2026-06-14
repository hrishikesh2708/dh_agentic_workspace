"use client";

import type { IntentAckMessage } from "@/lib/parse-agent-message";

export function IntentAckCard({ data }: { data: IntentAckMessage }) {
  // Build chip list in order: run_mode → sources → source_object → channels
  const chips: string[] = [];

  if (data.run_mode) chips.push(`Type: ${data.run_mode}`);
  if (data.sources?.length) chips.push(...data.sources.map((s) => `Source: ${s}`));
  if (data.source_object?.length) chips.push(...data.source_object);
  if (data.channels?.length) chips.push(...data.channels);

  if (chips.length === 0) return null;

  return (
    <div className="space-y-2 max-w-[85%]">
      <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
        Detected
      </p>
      <div className="flex flex-wrap gap-2">
        {chips.map((chip) => (
          <span
            key={chip}
            className="rounded-lg border border-[var(--border)] bg-[var(--muted)] px-3 py-1.5 text-sm font-medium text-[var(--foreground)]"
          >
            {chip}
          </span>
        ))}
      </div>
    </div>
  );
}
