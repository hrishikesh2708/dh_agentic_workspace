"use client";

import { AgentMessageBubble } from "@/components/chat/agent-message-bubble";
import { HitlApprovalCard } from "@/components/chat/hitl-approval-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useHeadlessInterrupt } from "@/hooks/use-headless-interrupt";
import { extractMessageText } from "@/lib/parse-agent-message";
import { useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { useCallback, useState } from "react";

export function HeadlessChat() {
  const { copilotkit } = useCopilotKit();
  const { agent } = useAgent();
  const { pending, resolve } = useHeadlessInterrupt();
  const [draft, setDraft] = useState("");

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || pending) return;

      agent.addMessage({
        role: "user",
        id: crypto.randomUUID(),
        content: trimmed,
      });
      void copilotkit.runAgent({ agent });
      setDraft("");
    },
    [agent, copilotkit, pending],
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(draft);
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-[var(--background)]">
      <header className="shrink-0 border-b border-[var(--border)] px-6 py-4">
        <h1 className="text-xl font-semibold text-[var(--foreground)]">
          Datahash Integrations
        </h1>
        <p className="text-sm text-[var(--muted-foreground)] mt-1">
          How can i help you with mappings?
        </p>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {agent.messages.length === 0 && (
          <p className="text-sm text-[var(--muted-foreground)]">
            Try: &quot; Map my salesforce leads to meta ads.&quot;
          </p>
        )}
        {agent.messages.map((message, index) => {
          const priorAssistant = agent.messages
            .slice(0, index)
            .filter((m) => m.role === "assistant")
            .map((m) => m.content);

          return (
            <div
              key={message.id}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {message.role === "user" ? (
                <div className="max-w-[85%] rounded-lg px-4 py-2 text-sm bg-[var(--primary)] text-[var(--primary-foreground)]">
                  <p className="whitespace-pre-wrap">
                    {extractMessageText(message.content)}
                  </p>
                </div>
              ) : (
                <AgentMessageBubble
                  content={message.content}
                  priorAssistantContents={priorAssistant}
                />
              )}
            </div>
          );
        })}
        {agent.isRunning && !pending && (
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
            <Spinner size="sm" />
            Agent is thinking…
          </div>
        )}
      </div>

      <footer className="shrink-0 border-t border-[var(--border)] px-6 py-4 space-y-3">
        {pending && (
          <HitlApprovalCard
            payload={pending.value}
            onApprove={(response) => resolve(response)}
            onReject={(reason) =>
              resolve({ approved: false, ...(reason ? { reason } : {}) })
            }
          />
        )}
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={
              pending
                ? "Approve or reject above to continue…"
                : "Message the agent…"
            }
            disabled={!!pending || agent.isRunning}
            className="flex-1"
          />
          <Button
            type="submit"
            disabled={!!pending || agent.isRunning || !draft.trim()}
          >
            Send
          </Button>
        </form>
      </footer>
    </div>
  );
}
