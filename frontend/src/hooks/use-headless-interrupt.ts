"use client";

import { CHAT_AGENT_ID } from "@/lib/chat-constants";
import { normalizeInterruptPayload } from "@/lib/normalize-interrupt-payload";
import { useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export { normalizeInterruptPayload } from "@/lib/normalize-interrupt-payload";

export const INTERRUPT_EVENT_NAME = "on_interrupt";

export type SelectOption = {
  id: string;
  label: string;
  enabled?: boolean;
  description?: string;
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
  cells: Record<string, MappingCell>;
};

export type UnresolvedField = {
  field: string;
  required: boolean;
  suggested_constant?: string;      // e.g. "USD" → chip "Set constant: USD"
  suggested_source_field?: string;  // e.g. "StageName = Closed Won" → chip "Map to: …"
};

export type ChannelConnectionStatus = {
  id: string;              // platform id / connector_slug e.g. "meta_capi"
  label: string;           // display name e.g. "Meta"
  status: string;          // "not_connected" | "skipped" | "connected"
  detail?: string;         // e.g. "Connected as Acme Business Mgr · ready"
  connector_slug?: string; // connector slug for the authorize endpoint
  project_id?: string;     // project_id scoping the OAuth flow
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
 * 1.  "select_channels"    pick ad platforms (multi-select chips)
 * 2.  "select_source"      pick CRM / source system (single-select chips)
 * 3.  "check_connection"   single source connection status (red/amber/green)
 * 4.  "select_object"      pick Salesforce object (single-select chips)
 * 5.  "check_channels"     multi-destination connection status (avatar rows)
 * 6.  "mapping_review"     review field mapping — single or multi destination
 * 7.  "canonical_mapping"  review canonical layer (inverted layout)
 * 8.  "resolve_fields"     fix unresolved fields (amber → green)
 * 9.  "funnel_prompt"      enable/disable funnel + pick trigger field
 * 10. "funnel_stages"      map picklist values to named funnel stages
 * 11. "validation_errors"  show validation errors, offer fix/skip/retry
 * 12. "activation_confirm" token-gated activation — user types UUID back
 * (legacy) "activate_confirm"  old validation+activate card (kept for compat)
 */
export type ApprovalInterruptPayload = {
  type?: string;
  phase?: string;
  default_selected?: string | string[];
  // generic approval
  proposal?: string;
  // mapping_review
  source_object?: string;
  // select_source | select_channels
  options?: SelectOption[] | string[];
  // select_object
  requested?: string;
  // select_channels (multi-select)
  min_select?: number;
  max_select?: number;
  // Common fields — present on most interrupt types
  title?: string;           // section label at top of card (e.g. "SALESFORCE OBJECT — SUGGESTED FIRST")
  message?: string;         // context question shown inside the card (all interrupt types)
  hint?: string;            // guidance shown below the options/list
  recommended?: string;     // pre-selected / suggested option id (source, object)
  confidence?: string;      // "high" | "medium" | "low" — badge on recommended option
  // check_connection
  source_label?: string;
  // "not_connected" | "expired" | "connected"
  connection_status?: string;
  account_detail?: string;  // e.g. "Acme Corp · john@acme.com" — shown when connected
  // mapping_review (row-based, single or multi-destination)
  destinations?: MappingDestination[];
  rows?: MappingReviewRow[] | Array<{
    canonical_key: string; label: string; source_field: string | null;
    status: string; cells: Record<string, { field: string | null; status: string }>;
  }>;
  source_fields?: string[]; // full list of available Salesforce fields for the dropdowns
  // canonical_mapping
  canonical_rows?: CanonicalMappingRow[];
  info_text?: string;  // shown as blue info bar inside the card
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
  // connect_source — OAuth handoff fields
  connector_slug?: string;
  project_id?: string;
  // funnel_prompt — enable/disable funnel + pick trigger field
  // resume: { enabled: bool, trigger_field: string | null }
  picklist_fields?: Array<{ name: string; label: string }>;
  suggested_trigger_field?: string;
  // funnel_stages — map picklist values to stage definitions
  // resume: { stages: [...] }
  trigger_field?: string;
  available_stage_values?: string[];
  suggested_stages?: Array<{
    stage_name: string; trigger_value: string;
    time_field?: string; value_field?: string;
    per_destination?: Record<string, unknown>;
  }>;
  datetime_fields?: string[];
  numeric_fields?: string[];
  active_destinations?: string[];
  // validation_errors — show errors/warnings, offer fix/skip/retry
  // resume: { action: "edit_mapping" | "skip_errors" | "retry" }
  errors?: string[];
  warnings?: string[];
  // activation_confirm — token-gated confirmation
  // resume: { token: str }
  token?: string;
  summary?: string[];
  // mapping_matrix (rows field above is shared — union covers both shapes)
  // google_ads_account
  accounts?: Array<{ value: string; label: string }>;
  // google_conversion_action
  conversion_actions?: Array<{ value: string; label: string }>;
  account_id?: string;
  // coverage_breakdown
  destinations_breakdown?: Array<{
    destination: string; coverage_pct: number;
    match_keys_covered: string[]; match_keys_missing: string[];
    status: string; required_count: number; mapped_count: number;
  }>;
  overall_pct?: number;
  // canonical_needs
  needs?: Array<{
    canonical_key: string; label: string; reason: string; status: string; required: boolean;
  }>;
  // validation_dry_run
  checks?: Array<{
    name: string; passed: boolean; severity: string; message: string;
    sample_payload?: Record<string, unknown>;
  }>;
  overall_passed?: boolean;
  // destination_metadata
  destination?: string;
  fields?: Array<{ name: string; label: string; placeholder?: string; required?: boolean }>;
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
