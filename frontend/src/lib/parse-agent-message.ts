import { parseJson } from "@copilotkit/shared";

// Field used in the mapping_complete agent message (distinct from interrupt payloads)
export type MappingField = {
  source_field: string;
  destination_field: string | null;
  confidence?: number;
  status?: string; // "auto_approved" | "human_reviewed" | "missing" etc.
};

export type MappingCompleteMessage = {
  type: "mapping_complete";
  summary: string;
  source_label: string;
  source_object: string;
  channels: string[];        // ad platforms e.g. ["Meta"] or ["Meta", "Google"]; empty = canonical layer
  mappings: MappingField[];
  stats: {
    total: number;
    auto_approved: number;
    human_reviewed: number;
  };
  session_id?: number | null;
};

export type IntentAckMessage = {
  type: "intent_ack";
  // CRM sources — display labels, e.g. ["Salesforce"]
  sources?: string[];
  // CRM record types, e.g. ["Opportunity", "Lead"]
  source_object?: string[];
  // Run config
  run_mode?: string;        // e.g. "Offline conversion"
  // Ad platforms
  channels?: string[];      // e.g. ["Meta", "Google"]
};

export type AgentEventMessage = {
  type: "agent_event";
  message: string;           // line text shown in chat
  status?: string;           // "in_progress" | "done" — drives italic/normal style
  step_index?: number;       // used to derive dynamic header subtitle
  step_total?: number;       // used to derive dynamic header subtitle
  event?: string;            // optional slug e.g. "schema_fetched" — for backend use
};

export type ThinkingMessage = {
  type: "thinking";
  message: string;        // "Analyzing your Salesforce schema…"
  step?: number;
  total_steps?: number;
};

export type StepCompleteMessage = {
  type: "step_complete";
  message: string;        // "Meta + Google selected as destinations"
  detail?: string;
};

export type SchemaSummaryMessage = {
  type: "schema_summary";
  source_label: string;
  source_object: string;
  total_fields: number;
  required_fields: number;
  sample_fields?: string[];
};

export type PipelineActivatedMessage = {
  type: "pipeline_activated";
  pipeline_name?: string;
  source_label: string;
  source_object: string;
  channels: string[];        // ad platforms e.g. ["Meta", "Google"]
  total_fields: number;
  mapped_fields: number;
};

export type ErrorMessage = {
  type: "error";
  title: string;
  message: string;
};

export type WarningMessage = {
  type: "warning";
  title: string;
  message: string;
};

// --- Intent-phase message types ---

/** Emitted by parse_initial_intent (intent_clarify) and handle_clarification (clarification_needed) */
export type ClarificationMessage = {
  type: "clarification_needed" | "intent_clarify";
  message: string;
  pending_slot?: string;
  attempt?: number;
  event?: string;
  phase?: string;
};

/** Emitted by handle_clarification when a slot is successfully resolved */
export type ClarificationResolvedMessage = {
  type: "clarification_resolved";
  message: string;
  resolved_slot: string;
  resolved_value: unknown;
  event?: string;
  phase?: string;
};

/** Emitted by confirm_intent — shows a structured summary for user sign-off */
export type IntentSummaryMessage = {
  type: "intent_summary";
  message: string;
  title?: string;
  event?: string;
  phase?: string;
  details?: {
    signal_type?: string;
    signal_display?: string;
    source?: string;
    source_label?: string;
    source_object?: string;
    destinations?: string[];
    destination_labels?: string[];
  };
  actions?: Array<{ id: string; label: string; style: string }>;
};

/** Emitted by handle_confirmation (complete / correction / reset) */
export type IntentStatusMessage = {
  type: "intent_complete" | "intent_correction" | "intent_reset";
  message: string;
  corrected_fields?: string[];
  event?: string;
  phase?: string;
};


export type ParsedAgentMessage =
  | { kind: "text"; text: string }
  | { kind: "mapping_complete"; data: MappingCompleteMessage }
  | { kind: "intent_ack"; data: IntentAckMessage }
  | { kind: "agent_event"; data: AgentEventMessage }
  | { kind: "thinking"; data: ThinkingMessage }
  | { kind: "step_complete"; data: StepCompleteMessage }
  | { kind: "schema_summary"; data: SchemaSummaryMessage }
  | { kind: "pipeline_activated"; data: PipelineActivatedMessage }
  | { kind: "error"; data: ErrorMessage }
  | { kind: "warning"; data: WarningMessage }
  | { kind: "clarification"; data: ClarificationMessage }
  | { kind: "clarification_resolved"; data: ClarificationResolvedMessage }
  | { kind: "intent_summary"; data: IntentSummaryMessage }
  | { kind: "intent_status"; data: IntentStatusMessage };

export function extractMessageText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === "string") return part;
        if (part && typeof part === "object" && "text" in part) {
          return String((part as { text?: string }).text ?? "");
        }
        return "";
      })
      .filter(Boolean)
      .join("\n");
  }
  if (content && typeof content === "object") return JSON.stringify(content);
  return "";
}

export function parseAgentMessage(content: unknown): ParsedAgentMessage {
  const text = extractMessageText(content).trim();
  if (!text) return { kind: "text", text: "" };

  const parsed = parseJson(text, null);
  if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
    const obj = parsed as Record<string, unknown>;

    if (obj.type === "mapping_complete") {
      return { kind: "mapping_complete", data: parsed as MappingCompleteMessage };
    }

    if (obj.type === "intent_ack") {
      return { kind: "intent_ack", data: parsed as IntentAckMessage };
    }

    if (obj.type === "agent_event") {
      return { kind: "agent_event", data: parsed as AgentEventMessage };
    }

    if (obj.type === "thinking") {
      return { kind: "thinking", data: parsed as ThinkingMessage };
    }

    if (obj.type === "step_complete") {
      return { kind: "step_complete", data: parsed as StepCompleteMessage };
    }

    if (obj.type === "schema_summary") {
      return { kind: "schema_summary", data: parsed as SchemaSummaryMessage };
    }

    if (obj.type === "pipeline_activated") {
      return { kind: "pipeline_activated", data: parsed as PipelineActivatedMessage };
    }

    if (obj.type === "error") {
      return { kind: "error", data: parsed as ErrorMessage };
    }

    if (obj.type === "warning") {
      return { kind: "warning", data: parsed as WarningMessage };
    }

    // --- Intent-phase message types ---

    if (obj.type === "clarification_needed" || obj.type === "intent_clarify") {
      return { kind: "clarification", data: parsed as ClarificationMessage };
    }

    if (obj.type === "clarification_resolved") {
      return { kind: "clarification_resolved", data: parsed as ClarificationResolvedMessage };
    }

    if (obj.type === "intent_summary") {
      return { kind: "intent_summary", data: parsed as IntentSummaryMessage };
    }

    if (
      obj.type === "intent_complete" ||
      obj.type === "intent_correction" ||
      obj.type === "intent_reset"
    ) {
      return { kind: "intent_status", data: parsed as IntentStatusMessage };
    }

  }

  return { kind: "text", text };
}
