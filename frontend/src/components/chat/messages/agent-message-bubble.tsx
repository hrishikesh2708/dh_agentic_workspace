"use client";

import { AgentEventLine } from "./agent-event-line";
import { IntentAckCard } from "../interrupts/intent-ack-card";
import { MappingResultCard } from "./mapping-result-card";
import {
  isRedundantConfirmedEvent,
  parseAgentMessage,
} from "@/lib/parse-agent-message";

export function AgentMessageBubble({
  content,
  priorAssistantContents = [],
}: {
  content: unknown;
  priorAssistantContents?: unknown[];
}) {
  const parsed = parseAgentMessage(content);

  if (parsed.kind === "mapping_complete") {
    return <MappingResultCard data={parsed.data} />;
  }

  if (parsed.kind === "intent_ack") {
    return <IntentAckCard data={parsed.data} />;
  }

  if (parsed.kind === "agent_event") {
    if (
      parsed.data.status === "confirmed" &&
      isRedundantConfirmedEvent(parsed.data, priorAssistantContents)
    ) {
      return null;
    }

    return <AgentEventLine data={parsed.data} />;
  }

  if (parsed.kind !== "text" || !parsed.text) return null;

  return (
    <div className="max-w-[85%] rounded-lg px-4 py-2 text-sm bg-[var(--secondary)] text-[var(--foreground)]">
      <p className="whitespace-pre-wrap">{parsed.text}</p>
    </div>
  );
}
