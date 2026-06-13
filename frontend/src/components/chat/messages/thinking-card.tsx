"use client";

import type { ThinkingMessage } from "@/lib/parse-agent-message";

export function ThinkingCard({ data }: { data: ThinkingMessage }) {
  return (
    <div className="flex items-center gap-3 max-w-[85%]">
      {/* Bouncing dots */}
      <div className="flex shrink-0 items-center gap-[3px]">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="h-[5px] w-[5px] rounded-full bg-[var(--muted-foreground)]/50 animate-bounce"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>

      <p className="text-sm text-[var(--muted-foreground)] italic leading-snug">{data.message}</p>

      {data.step !== undefined && data.total_steps !== undefined && (
        <span className="shrink-0 ml-auto rounded-full border border-[var(--border)] bg-[var(--muted)] px-2 py-0.5 text-[10px] font-medium text-[var(--muted-foreground)]">
          {data.step}/{data.total_steps}
        </span>
      )}
    </div>
  );
}
