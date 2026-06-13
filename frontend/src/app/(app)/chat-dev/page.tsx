/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║  DEV PREVIEW — DELETE THIS FILE when the agent emits real messages.     ║
 * ║                                                                         ║
 * ║  Route: /chat-dev                                                       ║
 * ║  Shows all chat message components (existing + new) with mock data      ║
 * ║  so you can iterate on UI without a live agent.                         ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 *
 * BACKEND CONTRACT — what your LangGraph agent should emit for each type:
 *
 * Agent messages are regular assistant messages containing a JSON string:
 *
 *   // Thinking / in-progress
 *   { "type": "thinking", "message": "Analyzing your Salesforce schema…", "step": 1, "total_steps": 4 }
 *
 *   // Step confirmed
 *   { "type": "step_complete", "message": "Meta + Google selected as destinations", "detail": "Optional sub-text" }
 *
 *   // CRM schema discovered
 *   { "type": "schema_summary", "source_label": "Salesforce", "source_object": "Opportunity",
 *     "total_fields": 47, "required_fields": 12, "sample_fields": ["Email", "Phone", ...] }
 *
 *   // Pipeline live
 *   { "type": "pipeline_activated", "pipeline_name": "Acme Prod — Opp → Meta + Google",
 *     "source_label": "Salesforce", "source_object": "Opportunity",
 *     "destinations": ["Meta CAPI", "Google Offline"], "total_fields": 47, "mapped_fields": 44 }
 *
 *   // Error
 *   { "type": "error", "title": "Connection failed", "message": "Could not reach Salesforce API." }
 *
 *   // Warning
 *   { "type": "warning", "title": "3 fields unmapped", "message": "You'll review these in the next step." }
 *
 *   // Intent acknowledged (existing)
 *   { "type": "intent_ack", "message": "...", "source_label": "Salesforce", "source_object": "Opportunity",
 *     "destination_label": "Meta CAPI", "complete": true, "subtitle": "Setup confirmed" }
 *
 *   // Agent event (existing)
 *   { "type": "agent_event", "event": "step", "message": "...",
 *     "phase": "canonical", "step": "map", "step_index": 2, "step_total": 4, "status": "in_progress" }
 *
 *   // Mapping complete (existing)
 *   { "type": "mapping_complete", "summary": "...", "source_label": "Salesforce",
 *     "source_object": "Opportunity", "destination_label": "Meta CAPI",
 *     "mapping_kind": "projection", "mappings": [...], "stats": { "total": 10, "auto_approved": 8, "human_reviewed": 2 } }
 */

"use client";

import { AgentEventCard } from "@/components/chat/messages/agent-event-card";
import { AgentEventLine } from "@/components/chat/messages/agent-event-line";
import { ErrorCard } from "@/components/chat/messages/error-card";
import { MappingResultCard } from "@/components/chat/messages/mapping-result-card";
import { PipelineActivatedCard } from "@/components/chat/messages/pipeline-activated-card";
import { SchemaSummaryCard } from "@/components/chat/messages/schema-summary-card";
import { StepCompleteCard } from "@/components/chat/messages/step-complete-card";
import { ThinkingCard } from "@/components/chat/messages/thinking-card";
import { WarningCard } from "@/components/chat/messages/warning-card";
import { IntentAckCard } from "@/components/chat/interrupts/intent-ack-card";
import type {
  AgentEventMessage,
  ErrorMessage,
  IntentAckMessage,
  MappingCompleteMessage,
  PipelineActivatedMessage,
  SchemaSummaryMessage,
  StepCompleteMessage,
  ThinkingMessage,
  WarningMessage,
} from "@/lib/parse-agent-message";

import type { MappingField } from "@/hooks/use-headless-interrupt";

// ── Mock data ──────────────────────────────────────────────────────────────

const MOCK_USER_MSG = "Set up Salesforce Opportunities → Meta and Google offline conversions";

const MOCK_AGENT_TEXT = "Sure! Let me walk you through the setup. I'll check your connections, map your fields, and activate the pipeline once everything looks good.";

const MOCK_THINKING: ThinkingMessage = {
  type: "thinking",
  message: "Analyzing your Salesforce Opportunity schema…",
  step: 2,
  total_steps: 4,
};

const MOCK_THINKING_SIMPLE: ThinkingMessage = {
  type: "thinking",
  message: "Checking Salesforce connection…",
};

const MOCK_STEP_COMPLETE: StepCompleteMessage = {
  type: "step_complete",
  message: "Meta + Google selected as destinations",
};

const MOCK_STEP_COMPLETE_DETAIL: StepCompleteMessage = {
  type: "step_complete",
  message: "Salesforce connected",
  detail: "Acme Business Manager · CRM CAPI ready",
};

const MOCK_SCHEMA_SUMMARY: SchemaSummaryMessage = {
  type: "schema_summary",
  source_label: "Salesforce",
  source_object: "Opportunity",
  total_fields: 47,
  required_fields: 12,
  sample_fields: ["Email", "Phone", "Amount", "CloseDate", "StageName", "GCLID", "AccountId", "OwnerId"],
};

const MOCK_PIPELINE_ACTIVATED: PipelineActivatedMessage = {
  type: "pipeline_activated",
  pipeline_name: "Acme Prod — Opportunity → Meta + Google",
  source_label: "Salesforce",
  source_object: "Opportunity",
  destinations: ["Meta CAPI", "Google Offline"],
  total_fields: 47,
  mapped_fields: 44,
};

const MOCK_ERROR: ErrorMessage = {
  type: "error",
  title: "Salesforce connection failed",
  message: "Could not reach the Salesforce API. Check that your OAuth token is valid and try reconnecting.",
};

const MOCK_WARNING: WarningMessage = {
  type: "warning",
  title: "3 fields couldn't be auto-mapped",
  message: "GCLID, conversion_event, and currency need your input — you'll review them in the next step.",
};

const MOCK_INTENT_ACK: IntentAckMessage = {
  type: "intent_ack",
  run_mode: "Offline conversion",
  source_label: "Salesforce",
  source_object: "Opportunity",
  destinations: ["Meta", "Google"],
};

const MOCK_EVENT_IN_PROGRESS: AgentEventMessage = {
  type: "agent_event",
  event: "step",
  message: "Generating canonical field mappings…",
  phase: "canonical",
  step: "map",
  step_index: 2,
  step_total: 4,
  status: "in_progress",
};

const MOCK_EVENT_CONFIRMED: AgentEventMessage = {
  type: "agent_event",
  event: "step",
  message: "Canonical mappings generated — 7 fields mapped automatically.",
  phase: "canonical",
  step: "map",
  step_index: 2,
  step_total: 4,
  status: "confirmed",
  source_label: "Salesforce",
  source_object: "Opportunity",
  destination_label: "Meta CAPI",
};

const MOCK_MAPPING_FIELDS: MappingField[] = [
  { source_field: "Contact.Email",        destination_field: "email",        confidence: 0.98, status: "auto_approved"  },
  { source_field: "Contact.Phone",        destination_field: "phone",        confidence: 0.96, status: "auto_approved"  },
  { source_field: "Amount",               destination_field: "value",        confidence: 0.91, status: "auto_approved"  },
  { source_field: "CloseDate",            destination_field: "event_time",   confidence: 0.95, status: "auto_approved"  },
  { source_field: "StageName=Closed Won", destination_field: "event_name",   confidence: 0.88, status: "human_reviewed" },
  { source_field: "— constant —",         destination_field: "currency",     confidence: 0.5,  status: "needs_review"   },
  { source_field: "GCLID",               destination_field: null,            confidence: 0.3,  status: "not_proposed"   },
];

const MOCK_MAPPING_COMPLETE: MappingCompleteMessage = {
  type: "mapping_complete",
  summary: "Field mapping complete — 6 of 7 fields mapped for Meta CAPI",
  source_label: "Salesforce",
  source_object: "Opportunity",
  destination_label: "Meta CAPI",
  mapping_kind: "projection",
  mappings: MOCK_MAPPING_FIELDS,
  stats: { total: 7, auto_approved: 5, human_reviewed: 1 },
};

// ── Sections ───────────────────────────────────────────────────────────────

type Section = { label: string; tag: string; node: React.ReactNode };

const SECTIONS: Section[] = [
  // ── New components ────────────────────────────────────────────────────────
  {
    label: "Thinking (with step counter)",
    tag: "thinking",
    node: <ThinkingCard data={MOCK_THINKING} />,
  },
  {
    label: "Thinking (simple)",
    tag: "thinking",
    node: <ThinkingCard data={MOCK_THINKING_SIMPLE} />,
  },
  {
    label: "Step complete",
    tag: "step_complete",
    node: <StepCompleteCard data={MOCK_STEP_COMPLETE} />,
  },
  {
    label: "Step complete (with detail)",
    tag: "step_complete",
    node: <StepCompleteCard data={MOCK_STEP_COMPLETE_DETAIL} />,
  },
  {
    label: "Schema summary",
    tag: "schema_summary",
    node: <SchemaSummaryCard data={MOCK_SCHEMA_SUMMARY} />,
  },
  {
    label: "Pipeline activated",
    tag: "pipeline_activated",
    node: <PipelineActivatedCard data={MOCK_PIPELINE_ACTIVATED} />,
  },
  {
    label: "Error",
    tag: "error",
    node: <ErrorCard data={MOCK_ERROR} />,
  },
  {
    label: "Warning",
    tag: "warning",
    node: <WarningCard data={MOCK_WARNING} />,
  },
  // ── Existing components ───────────────────────────────────────────────────
  {
    label: "Plain text — user bubble",
    tag: "user_text",
    node: (
      <div className="flex justify-end w-full">
        <div className="max-w-[85%] rounded-2xl bg-[var(--muted)] px-5 py-4 text-sm text-[var(--foreground)]">
          <p className="whitespace-pre-wrap">{MOCK_USER_MSG}</p>
        </div>
      </div>
    ),
  },
  {
    label: "Plain text — agent bubble",
    tag: "agent_text",
    node: (
      <div className="max-w-[85%] rounded-2xl border border-[var(--border)] bg-[var(--card)] px-5 py-4 text-sm text-[var(--foreground)] shadow-sm">
        <p className="whitespace-pre-wrap">{MOCK_AGENT_TEXT}</p>
      </div>
    ),
  },
  {
    label: "Intent ack — detected chips",
    tag: "intent_ack",
    node: <IntentAckCard data={MOCK_INTENT_ACK} />,
  },
  {
    label: "Agent event line — in progress",
    tag: "agent_event",
    node: <AgentEventLine data={MOCK_EVENT_IN_PROGRESS} />,
  },
  {
    label: "Agent event line — confirmed",
    tag: "agent_event",
    node: <AgentEventLine data={MOCK_EVENT_CONFIRMED} />,
  },
  {
    label: "Agent event card — in progress",
    tag: "agent_event_card",
    node: <AgentEventCard data={MOCK_EVENT_IN_PROGRESS} />,
  },
  {
    label: "Agent event card — confirmed",
    tag: "agent_event_card",
    node: <AgentEventCard data={MOCK_EVENT_CONFIRMED} />,
  },
  {
    label: "Mapping result card",
    tag: "mapping_complete",
    node: <MappingResultCard data={MOCK_MAPPING_COMPLETE} />,
  },
];

// ── Page ───────────────────────────────────────────────────────────────────

export default function ChatDevPage() {
  return (
    <div className="h-full overflow-y-auto bg-[var(--background)] px-6 py-8">
      {/* Banner */}
      <div className="mx-auto mb-8 max-w-2xl rounded-lg border border-dashed border-red-400/60 bg-red-500/5 px-4 py-3">
        <p className="text-sm font-semibold text-red-600 dark:text-red-400">
          🗑️ DEV PREVIEW — delete <code className="font-mono">src/app/(app)/chat-dev/</code> when your agent emits real messages
        </p>
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
          All chat message component types shown below with mock data. Backend contract documented in the page file.
        </p>
      </div>

      <div className="mx-auto max-w-2xl space-y-10">
        {SECTIONS.map((section, index) => (
          <section key={`${section.tag}-${index}`}>
            {/* Section header */}
            <div className="mb-3 flex items-center gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--secondary)] text-xs font-bold text-[var(--foreground)]">
                {index + 1}
              </span>
              <div>
                <p className="text-sm font-semibold text-[var(--foreground)]">{section.label}</p>
                <code className="text-xs text-[var(--muted-foreground)]">type: &quot;{section.tag}&quot;</code>
              </div>
            </div>

            {/* Component */}
            <div className="flex flex-col gap-2">
              {section.node}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
