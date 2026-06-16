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
import { CopilotKitCoreRuntimeConnectionStatus } from "@copilotkit/core";
import { HttpAgent } from "@ag-ui/client";
import { useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";

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
  const lastConnectedAgentRef = useRef<typeof agent | null>(null);
  const { pending, resolve } = useHeadlessInterrupt(sessionId);
  const [draft, setDraft] = useState("");
  // Optimistic user message — shown immediately on send, cleared once it
  // appears in agent.messages (which lags due to server round-trip).
  const [optimisticUserMsg, setOptimisticUserMsg] = useState<string | null>(null);

  // ── Picker interrupt context (message + hint) ──────────────────────────────
  // Captured into state the moment a picker interrupt arrives so the bubbles
  // survive after `pending` clears when the user confirms their selection.
  // Each entry records `afterIndex` = the last message index at capture time,
  // so the bubbles are inserted at the right position in the thread.
  const PICKER_TYPES = new Set(["select_source", "select_object", "select_channels"]);
  type InterruptContext = { afterIndex: number; message?: string; hint?: string };
  const [interruptContexts, setInterruptContexts] = useState<InterruptContext[]>([]);
  const pendingProcessedRef = useRef(false);

  useEffect(() => {
    if (!pending?.value?.type) {
      pendingProcessedRef.current = false; // reset so next interrupt is processed
      return;
    }
    if (!PICKER_TYPES.has(pending.value.type)) return;
    if (pendingProcessedRef.current) return; // already captured this interrupt
    pendingProcessedRef.current = true;

    const p = pending.value as { message?: string; hint?: string };
    if (!p.message && !p.hint) return;

    setInterruptContexts((prev) => [
      ...prev,
      {
        afterIndex: agent.messages.length - 1, // insert after the current last message
        message: p.message,
        hint: p.hint,
      },
    ]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending]);

  // ── Group consecutive same-prefix confirmed events ───────────────────────────
  // e.g. "Destination: Meta" + "Destination: Google" → "Destinations: Meta, Google"
  // `originalIndex` maps back to agent.messages so interruptContexts stay aligned.
  type DisplayMessage = { message: (typeof agent.messages)[0]; originalIndex: number; mergedContent?: string };
  const displayMessages = useMemo<DisplayMessage[]>(() => {
    const result: DisplayMessage[] = [];
    let i = 0;
    while (i < agent.messages.length) {
      const msg = agent.messages[i];
      if (msg.role === "assistant") {
        const parsed = parseAgentMessage(msg.content);
        if (parsed.kind === "agent_event" && parsed.data.status === "confirmed") {
          const text = parsed.data.message;
          const colonIdx = text.indexOf(": ");
          if (colonIdx !== -1) {
            const prefix = text.slice(0, colonIdx);
            const firstValue = text.slice(colonIdx + 2);
            const values = [firstValue];
            let j = i + 1;
            while (j < agent.messages.length) {
              const next = agent.messages[j];
              if (next.role !== "assistant") break;
              const nextParsed = parseAgentMessage(next.content);
              if (!(nextParsed.kind === "agent_event" && nextParsed.data.status === "confirmed" && nextParsed.data.message.startsWith(prefix + ": "))) break;
              values.push(nextParsed.data.message.slice(colonIdx + 2));
              j++;
            }
            if (values.length > 1) {
              result.push({
                message: msg,
                originalIndex: i,
                mergedContent: JSON.stringify({ type: "agent_event", message: `${prefix}s: ${values.join(", ")}`, status: "confirmed" }),
              });
              i = j;
              continue;
            }
          }
        }
      }
      result.push({ message: msg, originalIndex: i });
      i++;
    }
    return result;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agent.messages]);

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
    if (
      !sessionId ||
      !agent ||
      agent === lastConnectedAgentRef.current ||
      copilotkit.runtimeConnectionStatus !==
        CopilotKitCoreRuntimeConnectionStatus.Connected
    ) {
      return;
    }

    let detached = false;
    lastConnectedAgentRef.current = agent;

    const connectAbortController = new AbortController();
    if (agent instanceof HttpAgent) {
      agent.abortController = connectAbortController;
    }

    void (async () => {
      try {
        await copilotkit.connectAgent({ agent });
        if (detached) return;

        const hasAssistant = agent.messages.some((m) => m.role === "assistant");
        if (!hasAssistant && !agent.isRunning) {
          await copilotkit.runAgent({ agent });
        }
      } catch (error) {
        if (detached) return;
        lastConnectedAgentRef.current = null;
        console.error("HeadlessChat: connectAgent failed", error);
      }
    })();

    return () => {
      detached = true;
      lastConnectedAgentRef.current = null;
      connectAbortController.abort();
      void agent.detachActiveRun?.();
    };
  }, [agent, copilotkit, sessionId, copilotkit.runtimeConnectionStatus]);

  // Clear optimistic bubble once the server echoes the message back.
  useEffect(() => {
    if (!optimisticUserMsg) return;
    const arrived = agent.messages.some(
      (m) => m.role === "user" && extractMessageText(m.content) === optimisticUserMsg,
    );
    if (arrived) setOptimisticUserMsg(null);
  }, [agent.messages, optimisticUserMsg]);

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || pending) return;

      setOptimisticUserMsg(trimmed); // render immediately, before runAgent resets messages
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
        {displayMessages.map(({ message, originalIndex, mergedContent }) => {
          const priorAssistant = agent.messages
            .slice(0, originalIndex)
            .filter((m) => m.role === "assistant")
            .map((m) => m.content);

          // Interrupt context bubbles inserted AFTER this message's original index.
          // Captured when the interrupt fired; persist after pending clears.
          const contextsHere = interruptContexts.filter((c) => c.afterIndex === originalIndex);

          return (
            <Fragment key={message.id}>
              <div className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                {message.role === "user" ? (
                  <div className="max-w-[85%] rounded-2xl bg-[var(--muted)] px-5 py-4 text-sm text-[var(--foreground)]">
                    <p className="whitespace-pre-wrap">
                      {extractMessageText(message.content)}
                    </p>
                  </div>
                ) : (
                  <AgentMessageBubble
                    content={mergedContent ?? message.content}
                    priorAssistantContents={priorAssistant}
                  />
                )}
              </div>

              {contextsHere.map((ctx, ci) => (
                <Fragment key={`ictx-${originalIndex}-${ci}`}>
                  {ctx.message && (
                    <div className="flex justify-start">
                      <div className="max-w-[85%] rounded-2xl border border-[var(--border)] bg-[var(--card)] px-5 py-4 text-sm text-[var(--foreground)] shadow-sm">
                        <p className="whitespace-pre-wrap">{ctx.message}</p>
                      </div>
                    </div>
                  )}
                  {ctx.hint && (
                    <div className="flex justify-start">
                      <div className="max-w-[85%] rounded-2xl border border-[var(--border)] bg-[var(--muted)] px-5 py-3 text-sm text-[var(--muted-foreground)] shadow-sm">
                        <p className="whitespace-pre-wrap italic">{ctx.hint}</p>
                      </div>
                    </div>
                  )}
                </Fragment>
              ))}
            </Fragment>
          );
        })}

        {/* Optimistic user bubble — visible immediately after send, before
            the server round-trip echoes the message back into agent.messages */}
        {optimisticUserMsg && (
          <div className="flex justify-end">
            <div className="max-w-[85%] rounded-2xl bg-[var(--muted)] px-5 py-4 text-sm text-[var(--foreground)]">
              <p className="whitespace-pre-wrap">{optimisticUserMsg}</p>
            </div>
          </div>
        )}

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
