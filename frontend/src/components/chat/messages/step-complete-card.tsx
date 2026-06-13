"use client";

import type { StepCompleteMessage } from "@/lib/parse-agent-message";

export function StepCompleteCard({ data }: { data: StepCompleteMessage }) {
  return (
    <div className="flex items-start gap-2.5 max-w-[85%]">
      {/* Green check */}
      <span className="mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-green-600 text-[9px] font-bold text-white leading-none">
        ✓
      </span>

      <div className="space-y-0.5">
        <p className="text-sm font-medium text-[var(--foreground)]">{data.message}</p>
        {data.detail && (
          <p className="text-xs text-[var(--muted-foreground)]">{data.detail}</p>
        )}
      </div>
    </div>
  );
}
