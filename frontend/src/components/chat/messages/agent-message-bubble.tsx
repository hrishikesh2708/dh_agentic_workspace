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
import { parseAgentMessage } from "@/lib/parse-agent-message";

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

    case "agent_event":
      // Slot-confirmed events (source/object/destination gathered) → green check
      if (parsed.data.status === "confirmed") {
        return <StepCompleteCard data={{ type: "step_complete", message: parsed.data.message }} />;
      }
      return <AgentEventLine data={parsed.data} />;

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

    // Clarification question from the agent — plain text bubble
    case "clarification":
      return (
        <div className="max-w-[85%] rounded-2xl border border-[var(--border)] bg-[var(--card)] px-5 py-4 text-sm text-[var(--foreground)] shadow-sm">
          <p className="whitespace-pre-wrap">{parsed.data.message}</p>
        </div>
      );

    // Slot resolved — green check acknowledgement
    case "clarification_resolved":
      return (
        <StepCompleteCard
          data={{ type: "step_complete", message: parsed.data.message }}
        />
      );

    // All slots gathered — show message + detected chips (IntentAckCard)
    case "intent_summary": {
      const d = parsed.data;
      const details = d.details ?? {};
      // Adapt intent_summary details → IntentAckMessage shape
      const ackData = {
        type: "intent_ack" as const,
        run_mode: details.signal_display
          ? details.signal_display.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
          : undefined,
        sources: details.source_label ? [details.source_label] : undefined,
        source_object: details.source_object ? [details.source_object] : undefined,
        channels: details.destination_labels?.length ? details.destination_labels : undefined,
      };
      return (
        <div className="space-y-3 max-w-[85%]">
          {/* Confirmation question */}
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] px-5 py-4 text-sm text-[var(--foreground)] shadow-sm">
            <p className="whitespace-pre-wrap">{d.message}</p>
          </div>
          {/* Detected chips */}
          <IntentAckCard data={ackData} />
        </div>
      );
    }

    // intent_complete → green check
    // intent_correction → green check with what changed as detail
    // intent_reset → plain text ("let's start fresh")
    case "intent_status": {
      const { type, message, corrected_fields } = parsed.data;
      if (type === "intent_reset") {
        return (
          <div className="max-w-[85%] rounded-2xl border border-[var(--border)] bg-[var(--card)] px-5 py-4 text-sm text-[var(--foreground)] shadow-sm">
            <p className="whitespace-pre-wrap">{message}</p>
          </div>
        );
      }
      const detail =
        corrected_fields && corrected_fields.length > 0
          ? `Updated: ${corrected_fields.map((f) => f.replace(/_/g, " ")).join(", ")}`
          : undefined;
      return (
        <StepCompleteCard
          data={{ type: "step_complete", message, detail }}
        />
      );
    }

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
