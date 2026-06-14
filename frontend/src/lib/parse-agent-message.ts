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
  | { kind: "warning"; data: WarningMessage };

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

  }

  return { kind: "text", text };
}
