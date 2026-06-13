"use client";

import { AgentEventLine } from "./agent-event-line";
import { ErrorCard } from "./error-card";
import { IntentAckCard } from "../interrupts/intent-ack-card";
import { MappingResultCard } from "./mapping-result-card";
import { PipelineActivatedCard } from "./pipeline-activated-card";
import { SchemaSummaryCard } from "./schema-summary-card";
import { StepCompleteCard } from "./step-complete-card";
import { ThinkingCard } from "./thinking-card";
import { WarningCard } from "./warning-card";
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

  switch (parsed.kind) {
    case "mapping_complete":
      return <MappingResultCard data={parsed.data} />;

    case "intent_ack":
      return <IntentAckCard data={parsed.data} />;

    case "agent_event": {
      if (
        parsed.data.status === "confirmed" &&
        isRedundantConfirmedEvent(parsed.data, priorAssistantContents)
      ) {
        return null;
      }
      return <AgentEventLine data={parsed.data} />;
    }

    case "thinking":
      return <ThinkingCard data={parsed.data} />;

    case "step_complete":
      return <StepCompleteCard data={parsed.data} />;

    case "schema_summary":
      return <SchemaSummaryCard data={parsed.data} />;

    case "pipeline_activated":
      return <PipelineActivatedCard data={parsed.data} />;

    case "error":
      return <ErrorCard data={parsed.data} />;

    case "warning":
      return <WarningCard data={parsed.data} />;

    case "text":
      if (!parsed.text) return null;
      return (
        <div className="max-w-[85%] rounded-2xl border border-[var(--border)] bg-[var(--card)] px-5 py-4 text-sm text-[var(--foreground)] shadow-sm">
          <p className="whitespace-pre-wrap">{parsed.text}</p>
        </div>
      );

    default:
      return null;
  }
}
