import { parseJson } from "@copilotkit/shared";
import type { MappingField } from "@/hooks/use-headless-interrupt";

export type MappingCompleteMessage = {
  type: "mapping_complete";
  summary: string;
  source_label: string;
  source_object: string;
  destination_label: string;
  destination_type?: string;
  mapping_kind: string;
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
  message: string;
  complete?: boolean;
  subtitle?: string;
  source?: string;
  source_label?: string;
  source_object?: string;
  destination_type?: string;
  destination_label?: string;
  run_mode?: string;
  phase?: string;
};

export type AgentEventMessage = {
  type: "agent_event";
  event: string;
  message: string;
  phase?: string;
  step?: string;
  step_index?: number;
  step_total?: number;
  status?: string;
  source?: string;
  source_label?: string;
  source_object?: string;
  destination_type?: string;
  destination_label?: string;
  run_mode?: string;
};

function isLeakedIntentParseJson(parsed: Record<string, unknown>): boolean {
  return (
    "source" in parsed &&
    "source_object" in parsed &&
    "destination" in parsed &&
    parsed.type === undefined
  );
}

function intentAckFromLeakedJson(parsed: Record<string, unknown>): IntentAckMessage {
  const source = String(parsed.source ?? "");
  const sourceObject = String(parsed.source_object ?? "");
  const destinationType = String(parsed.destination ?? "");

  return {
    type: "intent_ack",
    message: "I'll help you set up this data connection.",
    source,
    source_object: sourceObject,
    destination_type: destinationType,
  };
}

export type ParsedAgentMessage =
  | { kind: "text"; text: string }
  | { kind: "mapping_complete"; data: MappingCompleteMessage }
  | { kind: "intent_ack"; data: IntentAckMessage }
  | { kind: "agent_event"; data: AgentEventMessage };

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

    if (isLeakedIntentParseJson(obj)) {
      return { kind: "intent_ack", data: intentAckFromLeakedJson(obj) };
    }
  }

  return { kind: "text", text };
}

const PHASE_LABELS: Record<string, string> = {
  intent: "Intent",
  canonical: "Canonical",
  projection: "Projection",
};

const STEP_LABELS: Record<string, string> = {
  requirements: "Requirements",
  parse: "Parse",
  source: "Source",
  object: "Object",
  destination: "Destination",
  bridge: "Bridge",
  map: "Mapping",
  setup: "Setup",
};

export function formatAgentStepLabel(data: AgentEventMessage): string | null {
  if (!data.phase || !data.step) return null;
  const phaseName = PHASE_LABELS[data.phase] ?? data.phase;
  const stepName = STEP_LABELS[data.step] ?? data.step;
  if (
    data.step_index !== undefined &&
    data.step_total !== undefined &&
    data.step_total > 0 &&
    data.step_index > 0
  ) {
    return `${phaseName} · ${stepName} (${data.step_index}/${data.step_total})`;
  }
  return `${phaseName} · ${stepName}`;
}

/** @deprecated Use formatAgentStepLabel */
export const formatIntentStepLabel = formatAgentStepLabel;

/** Hide gather confirmed lines already covered by an earlier intent_ack narrator card. */
export function isRedundantConfirmedEvent(
  event: AgentEventMessage,
  priorAssistantContents: unknown[],
): boolean {
  if (event.status !== "confirmed") return false;
  if (event.step !== "source" && event.step !== "object") return false;

  for (const content of priorAssistantContents) {
    const parsed = parseAgentMessage(content);
    if (parsed.kind !== "intent_ack" || parsed.data.complete) continue;
    const ack = parsed.data;
    if (
      event.step === "source" &&
      ack.source_label &&
      event.source_label === ack.source_label
    ) {
      return true;
    }
    if (
      event.step === "object" &&
      ack.source_object &&
      event.source_object &&
      ack.source_object.toLowerCase() === event.source_object.toLowerCase()
    ) {
      return true;
    }
  }
  return false;
}
