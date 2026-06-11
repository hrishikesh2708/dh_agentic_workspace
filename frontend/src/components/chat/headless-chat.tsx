"use client";

import { AgentMessageBubble } from "@/components/chat/agent-message-bubble";
import { ChatErrorBoundary } from "@/components/chat/chat-error-boundary";
import { HitlApprovalCard } from "@/components/chat/hitl-approval-card";
import { Spinner } from "@/components/ui/spinner";
import { useProject } from "@/components/chat/project-context";
import { CopilotChatLayout } from "@/components/chat/copilot-chat-layout";
import { useHeadlessInterrupt } from "@/hooks/use-headless-interrupt";
import { CHAT_AGENT_ID } from "@/lib/chat-constants";
import { extractMessageText } from "@/lib/parse-agent-message";
import { useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { useCallback, useState } from "react";

export function HeadlessChat({
  projectName: projectNameProp,
}: {
  projectName?: string;
} = {}) {
  const { project } = useProject();
  const projectName = projectNameProp?.trim() || project.name?.trim() || "";
  const { copilotkit } = useCopilotKit();
  const { agent } = useAgent({ agentId: CHAT_AGENT_ID });
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
    <CopilotChatLayout
      projectName={projectName}
      draft={draft}
      onDraftChange={setDraft}
      onSubmit={handleSubmit}
      inputDisabled={!!pending || agent.isRunning}
      inputPlaceholder={
        pending
          ? "Approve or reject above to continue…"
          : "Message Signals Copilot…"
      }
      footerExtra={
        pending ? (
          <HitlApprovalCard
            payload={pending.value}
            onApprove={(response) => resolve(response)}
            onReject={(reason) =>
              resolve({ approved: false, ...(reason ? { reason } : {}) })
            }
          />
        ) : null
      }
    >
      <ChatErrorBoundary mode="inline" projectName={projectName}>
        {agent.messages.length === 0 && (
          <p className="text-sm text-[var(--muted-foreground)]">
            Try: &quot;Map my Salesforce leads to Meta ads.&quot;
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
                <div className="max-w-[85%] rounded-lg bg-[var(--primary)] px-4 py-2 text-sm text-[var(--primary-foreground)]">
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
        {agent.isRunning && (
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
            <Spinner size="sm" />
            {pending ? "Applying your selection…" : "Agent is thinking…"}
          </div>
        )}
      </ChatErrorBoundary>
    </CopilotChatLayout>
  );
}
