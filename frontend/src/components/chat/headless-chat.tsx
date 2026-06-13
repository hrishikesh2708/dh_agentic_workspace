"use client";

import { AgentMessageBubble } from "./messages/agent-message-bubble";
import { ChatErrorBoundary } from "./chat-error-boundary";
import { HitlApprovalCard } from "./interrupts/hitl-approval-card";
import { Spinner } from "@/components/ui/spinner";
import { useProject } from "@/components/project/project-context";
import { CopilotChatLayout } from "./copilot-chat-layout";
import { useHeadlessInterrupt } from "@/hooks/use-headless-interrupt";
import { CHAT_AGENT_ID } from "@/lib/chat-constants";
import { extractMessageText, parseAgentMessage } from "@/lib/parse-agent-message";
import { useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

// ── Step labels keyed by interrupt type (matches agreed sequence) ────────────
const INTERRUPT_STEPS: Record<string, { step: number; total: number; label: string }> = {
  select_channels:   { step: 1, total: 9, label: "Select ad platforms" },
  select_source:     { step: 2, total: 9, label: "Select CRM source" },
  check_connection:  { step: 3, total: 9, label: "Check source connection" },
  select_object:     { step: 4, total: 9, label: "Select Salesforce object" },
  check_channels:    { step: 5, total: 9, label: "Check destination connections" },
  mapping_review:    { step: 6, total: 9, label: "Review field mapping" },
  canonical_mapping: { step: 7, total: 9, label: "Canonical layer" },
  resolve_fields:    { step: 8, total: 9, label: "Resolve unmapped fields" },
  activate_confirm:  { step: 9, total: 9, label: "Activate pipeline" },
};

export function HeadlessChat({
  projectName: projectNameProp,
  sessionId,
}: {
  projectName?: string;
  sessionId: string;
}) {
  const { project } = useProject();
  const projectName = projectNameProp?.trim() || project.name?.trim() || "";
  const { copilotkit } = useCopilotKit();
  const { agent } = useAgent({ agentId: CHAT_AGENT_ID, threadId: sessionId });
  const connectedSessionRef = useRef<string | null>(null);
  const { pending, resolve } = useHeadlessInterrupt(sessionId);
  const [draft, setDraft] = useState("");

  // Derive the current step for the header subtitle.
  // Priority: active interrupt type > latest agent_event with step info > null
  const stepInfo = useMemo(() => {
    // 1. Active HITL interrupt — most authoritative
    if (pending?.value?.type) {
      const info = INTERRUPT_STEPS[pending.value.type as string];
      if (info) return info;
    }

    // 2. Scan messages in reverse for an agent_event with step counters
    for (let i = agent.messages.length - 1; i >= 0; i--) {
      const msg = agent.messages[i];
      if (msg.role !== "assistant") continue;
      const parsed = parseAgentMessage(msg.content);
      if (
        parsed.kind === "agent_event" &&
        parsed.data.step_index !== undefined &&
        parsed.data.step_total !== undefined
      ) {
        return {
          step: parsed.data.step_index,
          total: parsed.data.step_total,
          label: parsed.data.message,
        };
      }
      if (
        parsed.kind === "thinking" &&
        parsed.data.step !== undefined &&
        parsed.data.total_steps !== undefined
      ) {
        return {
          step: parsed.data.step,
          total: parsed.data.total_steps,
          label: parsed.data.message,
        };
      }
    }

    return null;
  }, [pending, agent.messages]);

  useEffect(() => {
    if (!sessionId || connectedSessionRef.current === sessionId) return;

    let cancelled = false;
    connectedSessionRef.current = sessionId;

    void copilotkit.connectAgent({ agent }).catch((error: unknown) => {
      if (cancelled) return;
      connectedSessionRef.current = null;
      console.error("HeadlessChat: connectAgent failed", error);
    });

    return () => {
      cancelled = true;
    };
  }, [agent, copilotkit, sessionId]);

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
      stepInfo={stepInfo}
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
                <div className="max-w-[85%] rounded-2xl bg-[var(--muted)] px-5 py-4 text-sm text-[var(--foreground)]">
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
