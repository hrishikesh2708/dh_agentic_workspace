/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║  DEV PREVIEW — DELETE THIS FILE when the agent is ready to emit         ║
 * ║  real `on_interrupt` events via CopilotKit.                             ║
 * ║                                                                         ║
 * ║  Route: /interrupt-dev                                                  ║
 * ║  Shows all 6 interrupt card variants in sequence with mock data         ║
 * ║  so you can iterate on UI without a live agent.                         ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 *
 * BACKEND CONTRACT — what your LangGraph agent should emit for each type:
 *
 * interrupt("on_interrupt", {
 *
 *   // 1 — pick ad platforms (multi-select)
 *   type: "select_channels",
 *   options: [{ id, label, enabled }],   // enabled: false = "coming soon"
 *   min_select?: 1,
 *   default_selected?: string[],          // pre-selected IDs
 *   // → resume: { selected: string[] }
 *
 *   // 2 — pick CRM (single-select)
 *   type: "select_source",
 *   options: [{ id, label, enabled }],   // enabled: false = "coming soon"
 *   default_selected?: string,            // pre-selected ID
 *   // → resume: { selected: string }
 *
 *   // 3 — check source connection (3 variants)
 *   type: "check_connection",
 *   source_label: string,                 // e.g. "Salesforce"
 *   connection_status: "not_connected" | "expired" | "connected",
 *   message: string,                      // status description (stays in payload)
 *   account_detail?: string,              // e.g. "Acme Corp · john@acme.com" — connected only
 *   // → resume: onApprove({ action: "connect" }) | onReject("change_source")
 *
 *   // (remaining interrupts documented below each mock)
 * })
 *
 * Resume response shape (returned via command.resume):
 *   select_channels    → { selected: string[] }
 *   select_source      → { selected: string }
 *   check_connection   → { action: "connect" } | reject("change_source")
 *   select_object      → { selected: string }
 *   check_channels     → { action: "confirm_all" | "connect" | "skip", platform_id?: string }
 *   mapping_review     → { approved: true, rows: [...] } | { approved: false }
 *   canonical_mapping  → { approved: true } | { approved: true, skip_hints: true }
 *   resolve_fields     → { action: "submit", resolutions: [{ field, action: "set_constant"|"map_field", value?|source_field? }] }
 *                       // agent re-fires if more unresolved fields remain
 *                    OR { action: "confirm" } (resolved state → agent received confirm)
 *   activate_confirm   → { action: "activate" } | reject("review_matrix")
 *   confirm_run        → { approved: true, reason?: "..." }
 *                     OR { approved: false, reason?: "..." }
 *   generic            → { approved: true, reason?: "..." }
 *                     OR { approved: false, reason?: "..." }
 */

"use client";

import { useState } from "react";
import { HitlApprovalCard } from "@/components/chat/interrupts/hitl-approval-card";
import type { ApprovalInterruptPayload } from "@/hooks/use-headless-interrupt";

// ── Mock payloads (one per interrupt type) ─────────────────────────────────

// ── 2. select_source ──────────────────────────────────────────────────────
// Agent sends a plain chat message first, then fires this interrupt.
// No title/message/hint in payload — those belong in the chat thread.
//
// Inbound:  { type, options, default_selected? }
// Outbound: { selected: string }   e.g. "salesforce"
const MOCK_SELECT_SOURCE: ApprovalInterruptPayload = {
  type: "select_source",
  default_selected: "salesforce",
  options: [
    { id: "salesforce", label: "Salesforce",   enabled: true  },
    { id: "hubspot",    label: "HubSpot",       enabled: true  },
    { id: "marketo",    label: "Marketo",       enabled: false },
    { id: "dynamics",   label: "MS Dynamics",   enabled: false },
  ],
};

// ── 4. select_object ──────────────────────────────────────────────────────
// Agent sends a plain chat message first, then fires this interrupt.
// requested = agent's detected object from user's message — highlighted as
// "suggested" and moved first. Omit if agent cannot infer.
//
// Inbound:  { type, options: string[], requested?: string }
// Outbound: { selected: string }   e.g. "Opportunity"
const MOCK_SELECT_OBJECT: ApprovalInterruptPayload = {
  type: "select_object",
  requested: "opportunity",
  options: ["Opportunity", "Lead", "Contact", "Account", "Campaign", "CampaignMember"],
};


const SF_OPPORTUNITY_FIELDS = [
  "Contact.Email", "Contact.Phone", "Amount", "CloseDate",
  "StageName", "StageName=Closed Won", "GCLID", "AnnualRevenue",
  "AccountId", "OwnerId", "LeadSource", "— constant —",
];

// ── 6. mapping_review (2 variants) ───────────────────────────────────────
// Agent sends a plain chat message first, then fires this interrupt.
// source_fields powers the per-row source dropdown — send the full object field list.
// cells keyed by destination id; status drives the colour dot.
//
// Inbound:  { type, source_object, source_fields, destinations, rows }
// Outbound: { approved: true, rows: MappingReviewRow[] }   // rows with user overrides
//           onReject("edit_mapping")

// Variant A — single destination, one needs_input
const MOCK_MAPPING_REVIEW_SINGLE: ApprovalInterruptPayload = {
  type: "mapping_review",
  source_object: "Salesforce Opportunity",
  source_fields: SF_OPPORTUNITY_FIELDS,
  destinations: [{ id: "meta_capi", label: "Meta CRM CAPI" }],
  rows: [
    { source_field: "Contact.Email",       cells: { meta_capi: { field: "email (hashed)", status: "confident"   } } },
    { source_field: "Contact.Phone",       cells: { meta_capi: { field: "phone (hashed)", status: "confident"   } } },
    { source_field: "StageName=Closed Won",cells: { meta_capi: { field: "event_name",     status: "confident"   } } },
    { source_field: "CloseDate",           cells: { meta_capi: { field: "event_time",     status: "confident"   } } },
    { source_field: "Amount",              cells: { meta_capi: { field: "value",           status: "confident"   } } },
    { source_field: "— constant: USD —",   cells: { meta_capi: { field: "currency",        status: "needs_input" } } },
  ],
};

// Variant B — multi destination, mixed statuses + not_required cells
const MOCK_MAPPING_REVIEW_MULTI: ApprovalInterruptPayload = {
  type: "mapping_review",
  source_object: "Salesforce Opportunity",
  source_fields: SF_OPPORTUNITY_FIELDS,
  destinations: [
    { id: "meta_capi",      label: "Meta CRM CAPI"  },
    { id: "google_offline", label: "Google Offline"  },
  ],
  rows: [
    { source_field: "Contact.Email",       cells: { meta_capi: { field: "email (hashed)",           status: "confident"   }, google_offline: { field: "email (hashed)",          status: "confident"   } } },
    { source_field: "Contact.Phone",       cells: { meta_capi: { field: "phone (hashed)",           status: "confident"   }, google_offline: { field: "phone (hashed)",          status: "confident"   } } },
    { source_field: "Amount",              cells: { meta_capi: { field: "value",                    status: "confident"   }, google_offline: { field: "conversion value",        status: "confident"   } } },
    { source_field: "CloseDate",           cells: { meta_capi: { field: "event_time",               status: "confident"   }, google_offline: { field: "conversion_time",         status: "confident"   } } },
    { source_field: "StageName=Closed Won",cells: { meta_capi: { field: "event_name",               status: "confident"   }, google_offline: { field: "conversion action — pick", status: "needs_input" } } },
    { source_field: "— constant: USD —",   cells: { meta_capi: { field: "currency",                 status: "confident"   }, google_offline: { field: "currency",                status: "confident"   } } },
    { source_field: "GCLID (if present)",  cells: { meta_capi: { field: null,                       status: "not_required" }, google_offline: { field: "gclid",                 status: "needs_input" } } },
  ],
};

// ── 7. canonical_mapping ─────────────────────────────────────────────────
// Agent sends a plain chat message first, then fires this interrupt.
// source_fields powers the per-row dropdown — send the full object field list.
// info_text stays in payload — static inline explainer shown at the bottom.
//
// Inbound:  { type, canonical_rows, source_fields, info_text? }
// Outbound: { approved: true, rows: CanonicalMappingRow[] }  // with user overrides
const MOCK_CANONICAL_MAPPING: ApprovalInterruptPayload = {
  type: "canonical_mapping",
  source_fields: SF_OPPORTUNITY_FIELDS,
  canonical_rows: [
    { canonical_field: "Email",            description: "Required · all 5 destinations",                   status: "confident",   source_field: "Contact.Email"          },
    { canonical_field: "Phone",            description: "Recommended · all 5 · lifts match rate",          status: "confident",   source_field: "Contact.Phone"          },
    { canonical_field: "Conversion value", description: "Required · all 5",                                status: "confident",   source_field: "Amount"                 },
    { canonical_field: "Currency",         description: "Required · all 5",                                status: "confident",   source_field: "Constant: USD"          },
    { canonical_field: "Conversion time",  description: "Required · all 5",                                status: "confident",   source_field: "CloseDate"              },
    { canonical_field: "Conversion event", description: "Required · all 5 · Google needs an action match", status: "needs_input", source_field: "StageName = Closed Won" },
    { canonical_field: "Click ID (GCLID)", description: "Google & Microsoft only · matches the ad click",  status: "needs_input", source_field: "GCLID"                  },
  ],
  info_text: "Signals sends these to Meta, Google, TikTok, Snapchat & LinkedIn automatically — per-platform field names are handled for you.",
};


// ── 3. check_connection (3 variants) ─────────────────────────────────────
// message stays in the interrupt payload — it's status data, not intro text.
// account_detail is only sent when connection_status === "connected".
//
// Inbound:  { type, source_label, connection_status, message, account_detail? }
// Outbound: onApprove({ action: "connect" })   — connect / reconnect / continue
//           onReject("change_source")           — only shown when not connected
const MOCK_CHECK_CONNECTION_NONE: ApprovalInterruptPayload = {
  type: "check_connection",
  source_label: "Salesforce",
  connection_status: "not_connected",
  message:
    "No active connection found for project Acme Prod. I'll open the secure connect screen — your credentials stay on Datahash's existing authentication flow.",
};

const MOCK_CHECK_CONNECTION_EXPIRED: ApprovalInterruptPayload = {
  type: "check_connection",
  source_label: "Salesforce",
  connection_status: "expired",
  message:
    "Your Salesforce connection for project Acme Prod has expired. Reconnect to continue — your credentials stay on Datahash's existing authentication flow.",
};

const MOCK_CHECK_CONNECTION_OK: ApprovalInterruptPayload = {
  type: "check_connection",
  source_label: "Salesforce",
  connection_status: "connected",
  account_detail: "Acme Corp · john@acme.com",
  message:
    "Active connection found. The agent will use this to fetch your Salesforce schema.",
};

// ── 1. select_channels ────────────────────────────────────────────────────
// Agent sends a plain chat message first, then fires this interrupt.
// No title/message in payload — those belong in the chat thread.
//
// Inbound:  { type, options, min_select, default_selected? }
// Outbound: { selected: string[] }   e.g. ["meta", "google"]
const MOCK_SELECT_CHANNELS: ApprovalInterruptPayload = {
  type: "select_channels",
  min_select: 1,
  default_selected: ["meta"],          // pre-select Meta; agent can pass [] for none
  options: [
    { id: "meta",     label: "Meta",        enabled: true  },
    { id: "google",   label: "Google",      enabled: true  },
    { id: "tiktok",   label: "TikTok",      enabled: true  },
    { id: "snapchat", label: "Snapchat",    enabled: true  },
    { id: "linkedin", label: "LinkedIn",    enabled: true  },
    { id: "twitter",  label: "X (Twitter)", enabled: false }, // coming soon
    { id: "bing",     label: "Bing",        enabled: false }, // coming soon
  ],
};

// ── 5. check_channels (3 variants) ───────────────────────────────────────
// Agent sends a plain chat message first, then fires this interrupt.
// detail should always be present when connected (shows which account).
//
// Inbound:  { type, channels: ChannelConnectionStatus[] }
// Outbound: { action: "connect" | "skip" | "confirm_all", platform_id?: string }

// Variant A — some pending
const MOCK_CHECK_CHANNELS_MIXED: ApprovalInterruptPayload = {
  type: "check_channels",
  channels: [
    { id: "meta",   label: "Meta",   status: "connected",     detail: "Acme Business Manager · CRM CAPI ready" },
    { id: "google", label: "Google", status: "not_connected", detail: "No active connection · Offline Conversions" },
  ],
};

// Variant B — one expired
const MOCK_CHECK_CHANNELS_EXPIRED: ApprovalInterruptPayload = {
  type: "check_channels",
  channels: [
    { id: "meta",     label: "Meta",     status: "connected", detail: "Acme Business Manager · CRM CAPI ready" },
    { id: "tiktok",   label: "TikTok",   status: "expired",   detail: "Token expired 3 days ago · Events API" },
    { id: "linkedin", label: "LinkedIn", status: "connected", detail: "Acme Corp Page · Conversions API ready" },
  ],
};

// Variant C — all connected → green "All connected — continue" CTA
const MOCK_CHECK_CHANNELS_ALL_CONNECTED: ApprovalInterruptPayload = {
  type: "check_channels",
  channels: [
    { id: "meta",   label: "Meta",   status: "connected", detail: "Acme Business Manager · CRM CAPI ready" },
    { id: "google", label: "Google", status: "connected", detail: "Acme Ads · Offline Conversions ready" },
  ],
};

// ── 9. activate_confirm ───────────────────────────────────────────────────
// Inbound:  { type, validation?, summary_card?, confirm_label?, secondary_label? }
//   validation: green left-bar block with title + checks[]
//   summary_card: plain border block with title + lines[]
// Outbound: onApprove({ action: "activate" }) | onReject("review_matrix")
const MOCK_ACTIVATE_CONFIRM: ApprovalInterruptPayload = {
  type: "activate_confirm",
  validation: {
    title: "Validation passed — Meta + Google",
    checks: [
      "Source reachable · both credentials valid",
      "All required fields mapped across both destinations",
      "Sample payload well-formed for each Conversion API",
    ],
  },
  summary_card: {
    title: "Salesforce Opportunities → Meta + Google (one pipeline)",
    lines: [
      "Offline conversions · email/phone hashed · value=Amount, currency=USD",
      "Shared mapping reused; Google conversion action set to Closed Won",
      "Data flows forward from activation (no backfill in this setup).",
    ],
  },
  confirm_label: "Activate both",
  secondary_label: "Review matrix",
};

// ── 8 resolve_fields (has_issues) ──────────────────────────────────────────
// Inbound:  { type, resolve_status, destination_label, source_fields, unresolved_fields }
// Outbound: { action: "submit", resolutions: [{ field, action, value? | source_field? }] }
//   action per field: "set_constant" (value=…) | "map_field" (source_field=…)
// Agent re-fires this interrupt if more unresolved fields remain.
const MOCK_RESOLVE_FIELDS_ISSUES: ApprovalInterruptPayload = {
  type: "resolve_fields",
  resolve_status: "has_issues",
  destination_label: "Meta",
  source_fields: SF_OPPORTUNITY_FIELDS,
  unresolved_fields: [
    { field: "currency", required: true, suggested_constant: "USD" },
    { field: "stage_name", required: true, suggested_source_field: "StageName" },
    { field: "conversion_event", required: false },
  ],
};

const MOCK_RESOLVE_FIELDS_RESOLVED: ApprovalInterruptPayload = {
  type: "resolve_fields",
  resolve_status: "resolved",
  destination_label: "Meta",
  summary_text: "email, phone → hashed before sending. value=Amount, currency=USD",
};


const STAGES: { label: string; tag: string; payload: ApprovalInterruptPayload }[] = [
  // ── Agreed interrupt sequence ────────────────────────────────────────────
  { label: "1 — Select channels",                tag: "select_channels",  payload: MOCK_SELECT_CHANNELS          },
  { label: "2 — Select source CRM",              tag: "select_source",    payload: MOCK_SELECT_SOURCE            },
  { label: "3 — Check connection (not connected)",tag: "check_connection", payload: MOCK_CHECK_CONNECTION_NONE    },
  { label: "3 — Check connection (expired)",      tag: "check_connection", payload: MOCK_CHECK_CONNECTION_EXPIRED },
  { label: "3 — Check connection (connected)",    tag: "check_connection", payload: MOCK_CHECK_CONNECTION_OK      },
  { label: "4 — Select object",                  tag: "select_object",    payload: MOCK_SELECT_OBJECT            },
  { label: "5 — Check channels (mixed)",          tag: "check_channels",   payload: MOCK_CHECK_CHANNELS_MIXED         },
  { label: "5 — Check channels (with expired)",   tag: "check_channels",   payload: MOCK_CHECK_CHANNELS_EXPIRED       },
  { label: "5 — Check channels (all connected)",  tag: "check_channels",   payload: MOCK_CHECK_CHANNELS_ALL_CONNECTED },
  { label: "6 — Mapping review (single dest)",    tag: "mapping_review",   payload: MOCK_MAPPING_REVIEW_SINGLE   },
  { label: "6 — Mapping review (multi dest)",     tag: "mapping_review",   payload: MOCK_MAPPING_REVIEW_MULTI    },
  { label: "7 — Canonical mapping",               tag: "canonical_mapping",payload: MOCK_CANONICAL_MAPPING       },
  { label: "8 — Resolve fields (has issues)",     tag: "resolve_fields",   payload: MOCK_RESOLVE_FIELDS_ISSUES   },
  { label: "8 — Resolve fields (resolved)",       tag: "resolve_fields",   payload: MOCK_RESOLVE_FIELDS_RESOLVED },
  { label: "9 — Activate confirm",                tag: "activate_confirm", payload: MOCK_ACTIVATE_CONFIRM        },
];

// ── Preview page ───────────────────────────────────────────────────────────

export default function InterruptDevPage() {
  const [responses, setResponses] = useState<Record<number, unknown>>({});

  function handleApprove(index: number, response: unknown) {
    setResponses((prev) => ({ ...prev, [index]: { action: "approved", response } }));
  }

  function handleReject(index: number, reason?: string) {
    setResponses((prev) => ({ ...prev, [index]: { action: "rejected", reason } }));
  }

  return (
    <div className="h-full overflow-y-auto bg-[var(--background)] px-6 py-8">
      {/* Banner */}
      <div className="mx-auto mb-8 max-w-2xl rounded-lg border border-dashed border-red-400/60 bg-red-500/5 px-4 py-3">
        <p className="text-sm font-semibold text-red-600 dark:text-red-400">
          🗑️ DEV PREVIEW — delete <code className="font-mono">src/app/(app)/interrupt-dev/</code> when your agent emits real interrupts
        </p>
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
          Each card below shows a different interrupt type with mock data. The backend contract is documented in the page file.
        </p>
      </div>

      <div className="mx-auto max-w-2xl space-y-10">
        {STAGES.map((stage, index) => {
          const result = responses[index];
          return (
            <section key={stage.tag}>
              {/* Stage header */}
              <div className="mb-3 flex items-center gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--secondary)] text-xs font-bold text-[var(--foreground)]">
                  {index + 1}
                </span>
                <div>
                  <p className="text-sm font-semibold text-[var(--foreground)]">{stage.label}</p>
                  <code className="text-xs text-[var(--muted-foreground)]">type: &quot;{stage.tag}&quot;</code>
                </div>
              </div>

              {/* Card */}
              <HitlApprovalCard
                payload={stage.payload}
                onApprove={(response) => handleApprove(index, response)}
                onReject={(reason) => handleReject(index, reason)}
              />

              {/* Response echo */}
              {result ? (
                <pre className="mt-2 rounded-md border border-[var(--border)] bg-[var(--secondary)] p-3 text-xs text-[var(--foreground)] overflow-x-auto">
                  {JSON.stringify(result, null, 2)}
                </pre>
              ) : null}
            </section>
          );
        })}
      </div>
    </div>
  );
}
