"use client";

import { CHAT_AGENT_ID } from "@/lib/chat-constants";
import { normalizeInterruptPayload } from "@/lib/normalize-interrupt-payload";
import { useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export { normalizeInterruptPayload } from "@/lib/normalize-interrupt-payload";

export const INTERRUPT_EVENT_NAME = "on_interrupt";

export type MappingField = {
  source_field: string;
  destination_field?: string | null;
  confidence: number;
  reasoning?: string;
  transformation_needed?: string | null;
  validation_status?: string;
  validation_notes?: string[];
  status?: string;
};

export type SelectOption = {
  id: string;
  label: string;
  enabled?: boolean;
  description?: string;
};

export type DestinationFieldOption = {
  name: string;
  label?: string;
  type?: string;
  required?: boolean;
  description?: string;
};

export type MappingSummary = {
  total_source_fields: number;
  mapped: number;
  not_proposed: number;
  needs_review: number;
};

export type MappingDestination = {
  id: string;
  label: string;
  color?: string;
};

export type MappingCell = {
  field: string | null;
  status: string; // "confident" | "needs_input" | "missing" | "not_required"
};

export type MappingReviewRow = {
  source_field: string;
  is_constant?: boolean;
  cells: Record<string, MappingCell>;
};

export type UnresolvedField = {
  field: string;
  required: boolean;
  suggested_constant?: string; // e.g. "USD" — shown as "Set constant: USD"
};

export type ChannelConnectionStatus = {
  id: string;       // platform id e.g. "meta", "google"
  label: string;    // display name e.g. "Meta", "Google"
  status: string;   // "not_connected" | "expired" | "connected"
  detail?: string;  // e.g. "Connected as Acme Business Mgr · ready"
};

export type CanonicalMappingRow = {
  canonical_field: string;
  description?: string;
  status: string; // "confident" | "needs_input" | "missing"
  source_field?: string;
};

/**
 * Backend interrupt contract — what CopilotKit streams as `on_interrupt`.
 *
 * Interrupt sequence (agreed order):
 * ─────────────────────────────────────────────────────────────────────
 * 1. "select_channels"   pick ad platforms (multi-select chips)
 * 2. "select_source"     pick CRM / source system (single-select chips)
 * 3. "check_connection"  single source connection status (red/amber/green)
 * 4. "select_object"     pick Salesforce object (single-select chips)
 * 5. "check_channels"    multi-destination connection status (avatar rows)
 * 6. "mapping_review"    review field mapping — single or multi destination
 * 7. "canonical_mapping" review canonical layer (inverted layout)
 * 8. "resolve_fields"    fix unresolved fields (amber → green)
 * 9. "activate_confirm"  validation result + activate CTA
 */
export type ApprovalInterruptPayload = {
  type?: string;
  phase?: string;
  title?: string;
  message?: string;
  hint?: string;
  default_selected?: string;
  // generic approval
  proposal?: string;
  // mapping_review
  mapping_kind?: string;
  source_object?: string;
  destination_type?: string;
  destination_label?: string;
  mappings?: MappingField[];
  destination_fields?: DestinationFieldOption[];
  mapping_summary?: MappingSummary;
  // select_source | select_channels
  options?: SelectOption[] | string[];
  // select_object
  requested?: string;
  // select_channels (multi-select)
  min_select?: number;
  max_select?: number;
  // check_connection
  source_label?: string;
  // "not_connected" | "expired" | "connected"
  connection_status?: string;
  // mapping_review (row-based, single or multi-destination)
  destinations?: MappingDestination[];
  rows?: MappingReviewRow[];
  source_fields?: string[]; // full list of available Salesforce fields for the dropdowns
  // canonical_mapping
  canonical_rows?: CanonicalMappingRow[];
  info_text?: string;
  // resolve_fields
  // "has_issues" → amber, shows unresolved fields
  // "resolved"   → green, shows summary + confirm
  resolve_status?: string;
  unresolved_fields?: UnresolvedField[];
  summary_text?: string;
  destination_label?: string;
  // check_channels — multi-channel connection status
  // resume: { action: "confirm" | "connect" | "skip", platform_id: string }
  channels?: ChannelConnectionStatus[];
  // activate_confirm — validation result + pipeline summary before activating
  // resume: { action: "activate" } | { action: "review_matrix" }
  validation?: { title: string; checks: string[] };
  summary_card?: { title: string; lines: string[] };
  confirm_label?: string;
  secondary_label?: string;
};

export type InterruptEvent = {
  name: string;
  value: ApprovalInterruptPayload;
};

export function useHeadlessInterrupt(threadId?: string) {
  const { copilotkit } = useCopilotKit();
  const { agent } = useAgent({ agentId: CHAT_AGENT_ID, threadId });
  const [pending, setPending] = useState<InterruptEvent | null>(null);
  const stagedRef = useRef<InterruptEvent | null>(null);
  const rawInterruptRef = useRef<unknown>(null);

  useEffect(() => {
    const sub = agent.subscribe({
      onCustomEvent: ({ event }) => {
        if (event.name === INTERRUPT_EVENT_NAME) {
          rawInterruptRef.current = event.value;
          stagedRef.current = {
            name: event.name,
            value: normalizeInterruptPayload(event.value),
          };
        }
      },
      onRunStartedEvent: () => {
        stagedRef.current = null;
        rawInterruptRef.current = null;
        setPending(null);
      },
      onRunFinalized: () => {
        if (stagedRef.current) {
          setPending(stagedRef.current);
          stagedRef.current = null;
        }
      },
      onRunFailed: ({ error }) => {
        stagedRef.current = null;
        rawInterruptRef.current = null;
        console.error("Agent run failed after interrupt:", error);
      },
      onRunErrorEvent: ({ event }) => {
        console.error("Agent run error:", event.message);
      },
    });
    return () => sub.unsubscribe();
  }, [agent]);

  const clear = useCallback(() => {
    stagedRef.current = null;
    rawInterruptRef.current = null;
    setPending(null);
  }, []);

  const resolve = useCallback(
    (response: unknown) => {
      const snapshot = pending;
      setPending(null);
      void copilotkit
        .runAgent({
          agent,
          forwardedProps: {
            command: {
              resume: response,
              interruptEvent: rawInterruptRef.current ?? snapshot?.value,
            },
          },
        })
        .catch((error) => {
          console.error("Failed to resume agent after HITL:", error);
        });
    },
    [agent, copilotkit, pending],
  );

  return useMemo(
    () => ({ pending, resolve, clear }),
    [pending, resolve, clear],
  );
}
