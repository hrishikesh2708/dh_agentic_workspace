"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MOCK_ACTIVITY } from "@/lib/mock-workspace";
import { cn } from "@/lib/utils";

import { useShell } from "./shell-context";

type RightPanelTab = "activity" | "signals" | "ask";

const TABS: { id: RightPanelTab; label: string }[] = [
  { id: "activity", label: "Activity" },
  { id: "signals", label: "Signals" },
  { id: "ask", label: "Ask" },
];

function StatusDot({ status }: { status: "done" | "pending" | "waiting" }) {
  const color =
    status === "done"
      ? "bg-[var(--success)]"
      : status === "pending"
        ? "bg-[var(--warning)]"
        : "bg-[var(--muted-foreground)]/40";

  return <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", color)} />;
}

export function RightPanel() {
  const { rightPanelCollapsed, toggleRightPanel } = useShell();
  const [activeTab, setActiveTab] = useState<RightPanelTab>("activity");
  const [askDraft, setAskDraft] = useState("");

  if (rightPanelCollapsed) {
    return (
      <aside className="hidden h-screen w-10 shrink-0 flex-col border-l border-[var(--border)] bg-[var(--card)] md:flex">
        <div className="flex h-14 items-center justify-center border-b border-[var(--border)]">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleRightPanel}
            aria-label="Expand panel"
            className="h-8 w-8"
          >
            ‹
          </Button>
        </div>
        <div className="flex flex-1 flex-col items-center gap-2 py-3">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              title={tab.label}
              onClick={() => {
                setActiveTab(tab.id);
                toggleRightPanel();
              }}
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-[var(--radius)] text-xs font-medium transition-colors",
                activeTab === tab.id
                  ? "bg-[var(--secondary)] text-[var(--secondary-foreground)]"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)]",
              )}
            >
              {tab.label.charAt(0)}
            </button>
          ))}
        </div>
      </aside>
    );
  }

  return (
    <aside className="hidden h-screen w-80 shrink-0 flex-col border-l border-[var(--border)] bg-[var(--card)] md:flex">
      <div className="flex h-14 items-center justify-between border-b border-[var(--border)] px-3">
        <div className="flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "rounded-[var(--radius)] px-3 py-1.5 text-sm transition-colors",
                activeTab === tab.id
                  ? "border border-[var(--border)] bg-[var(--background)] font-medium text-[var(--foreground)]"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)]",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleRightPanel}
          aria-label="Collapse panel"
          className="h-8 w-8 shrink-0"
        >
          ›
        </Button>
      </div>

      <div className="flex flex-1 flex-col overflow-hidden">
        {activeTab === "activity" && (
          <>
            <div className="grid grid-cols-2 gap-2 border-b border-[var(--border)] p-3">
              <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--background)] p-3">
                <div className="text-lg font-semibold">1,247</div>
                <div className="text-xs text-[var(--muted-foreground)]">
                  Leads matched
                </div>
              </div>
              <div className="rounded-[var(--radius)] border border-[var(--border)] bg-[var(--background)] p-3">
                <div className="text-lg font-semibold">6/6</div>
                <div className="text-xs text-[var(--muted-foreground)]">
                  PII fields found
                </div>
              </div>
            </div>
            <div className="flex-1 space-y-3 overflow-y-auto p-3">
              {MOCK_ACTIVITY.map((item) => (
                <div
                  key={item.id}
                  className={cn(
                    "flex gap-2 text-sm",
                    item.status === "waiting" &&
                      "text-[var(--muted-foreground)]/60",
                  )}
                >
                  <StatusDot status={item.status} />
                  <div className="min-w-0 flex-1">
                    <div>{item.label}</div>
                    {item.time && (
                      <div className="text-xs text-[var(--muted-foreground)]">
                        {item.time}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {activeTab === "signals" && (
          <div className="flex flex-1 items-center justify-center p-6 text-sm text-[var(--muted-foreground)]">
            Signal report will appear here.
          </div>
        )}

        {activeTab === "ask" && (
          <div className="flex flex-1 flex-col p-3">
            <div className="flex flex-1 items-center justify-center text-sm text-[var(--muted-foreground)]">
              Ask questions about this pipeline.
            </div>
          </div>
        )}

        <div className="shrink-0 border-t border-[var(--border)] p-3">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setAskDraft("");
            }}
            className="flex gap-2"
          >
            <Input
              value={askDraft}
              onChange={(e) => setAskDraft(e.target.value)}
              placeholder="Ask about this pipeline…"
              className="flex-1"
            />
            <Button type="submit" size="icon" disabled={!askDraft.trim()}>
              ▣
            </Button>
          </form>
        </div>
      </div>
    </aside>
  );
}
