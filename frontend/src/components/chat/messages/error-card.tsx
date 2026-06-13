"use client";

import { Card, CardContent } from "@/components/ui/card";
import type { ErrorMessage } from "@/lib/parse-agent-message";

export function ErrorCard({ data }: { data: ErrorMessage }) {
  return (
    <Card className="w-full max-w-lg border-[var(--border)] bg-[var(--card)] shadow-sm overflow-hidden">
      <div className="flex">
        {/* Red left accent bar */}
        <div className="w-1 shrink-0 bg-red-500" />

        <CardContent className="p-4 space-y-1 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold tracking-widest text-red-600 dark:text-red-400 uppercase">
              Error
            </span>
          </div>
          <p className="text-sm font-semibold text-[var(--foreground)]">{data.title}</p>
          <p className="text-sm text-[var(--muted-foreground)]">{data.message}</p>
        </CardContent>
      </div>
    </Card>
  );
}
