"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MOCK_PROJECT_NAME } from "@/lib/mock-workspace";
import { cn } from "@/lib/utils";

export function CopilotChatLayout({
  children,
  draft = "",
  onDraftChange,
  onSubmit,
  inputDisabled = false,
  inputPlaceholder = "Message Signals Copilot…",
  banner,
  footerExtra,
}: {
  children?: React.ReactNode;
  draft?: string;
  onDraftChange?: (value: string) => void;
  onSubmit?: (e: React.FormEvent) => void;
  inputDisabled?: boolean;
  inputPlaceholder?: string;
  banner?: React.ReactNode;
  footerExtra?: React.ReactNode;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col bg-[var(--background)]">
      <header className="shrink-0 border-b border-[var(--border)]">
        <div className="mx-auto flex w-full max-w-4xl items-center justify-between gap-4 px-6 py-4">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--accent)] text-sm font-semibold text-[var(--accent-foreground)]">
              ●
            </span>
            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold text-[var(--foreground)]">
                Signals Setup Copilot
              </h1>
              <p className="text-sm text-[var(--muted-foreground)]">
                Step 1 · Start mapping setup
              </p>
            </div>
          </div>
          <p className="shrink-0 text-sm text-[var(--muted-foreground)]">
            Project: {MOCK_PROJECT_NAME}
          </p>
        </div>
      </header>

      {banner ? (
        <div className="shrink-0 border-b border-[var(--border)] bg-[var(--secondary)]/40 px-6 py-2">
          <div className="mx-auto max-w-4xl text-sm text-[var(--muted-foreground)]">
            {banner}
          </div>
        </div>
      ) : null}

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-4xl space-y-4 px-6 py-4">
          {children ?? (
            <p className="text-sm text-[var(--muted-foreground)]">
              Try: &quot;Map my Salesforce leads to Meta ads.&quot;
            </p>
          )}
        </div>
      </div>

      <footer className="shrink-0 border-t border-[var(--border)]">
        <div className="mx-auto w-full max-w-4xl space-y-3 px-6 py-4">
          {footerExtra}
          <form
            onSubmit={onSubmit}
            className="flex gap-2"
          >
            <Input
              value={draft}
              onChange={(e) => onDraftChange?.(e.target.value)}
              placeholder={inputPlaceholder}
              disabled={inputDisabled}
              className="flex-1"
            />
            <Button
              type="submit"
              disabled={inputDisabled || !draft.trim()}
            >
              ↑
            </Button>
          </form>
        </div>
      </footer>
    </div>
  );
}

export function CopilotOfflineBanner({
  message,
  className,
}: {
  message: string;
  className?: string;
}) {
  return (
    <p className={cn("text-sm", className)}>
      <span className="font-medium text-[var(--foreground)]">Preview mode.</span>{" "}
      {message}
    </p>
  );
}
