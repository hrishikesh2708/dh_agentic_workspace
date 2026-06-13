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
 *   // Phase 1 — pick CRM
 *   type: "select_source",
 *   title: "Choose your data source",
 *   message: "Select the CRM where your customer data lives.",
 *   hint?: "Don't see yours? More coming soon.",
 *   options: [{ id: "salesforce", label: "Salesforce", enabled: true }, ...],
 *   default_selected?: "salesforce",
 *
 *   // Phase 2 — pick Salesforce object
 *   type: "select_object",
 *   title: "Select Salesforce object",
 *   message: "Which object contains your customer records?",
 *   requested?: "lead",               // user's raw text hint
 *   options: ["Lead", "Contact", "Account", ...],
 *
 *   // Phase 3 — pick destination
 *   type: "select_destination",
 *   title: "Choose destination pipeline",
 *   message: "Where should the mapped data go?",
 *   options: [
 *     { id: "canonical",  label: "Canonical Store",          description: "..." },
 *     { id: "meta_capi",  label: "Meta Conversions API",     description: "..." },
 *     { id: "google_dm",  label: "Google DM",                description: "..." },
 *   ],
 *
 *   // Phase 4 — review field mappings
 *   type: "mapping_review",
 *   source_object: "Lead",
 *   destination_type: "meta_capi",
 *   destination_label: "Meta CAPI",
 *   mapping_kind: "canonical" | "projection",
 *   mappings: [
 *     { source_field, destination_field, confidence: 0–1,
 *       status: "auto_approved" | "needs_review" | "unmatched" | "not_proposed" },
 *     ...
 *   ],
 *   destination_fields: [{ name, label, type?, required?, description? }, ...],
 *   mapping_summary?: { total_source_fields, mapped, not_proposed, needs_review },
 *
 *   // Phase 5 — confirm before saving
 *   type: "confirm_run",
 *   title?: "Ready to save mappings",
 *   message?: "Review the summary, then approve to save and activate.",
 *   summary: {
 *     source: "Salesforce",
 *     source_object: "Lead",
 *     destination: "Meta CAPI",
 *     total_fields: 12,
 *     mapped_fields: 10,
 *     canonical_step: true,
 *     projection_step: true,
 *   },
 *
 *   // Fallback — generic approve/reject
 *   proposal: "Free-text description of what the agent wants to do.",
 * })
 *
 * Resume response shape (returned via command.resume):
 *   select_source      → { selected: "salesforce" }
 *   select_object      → { selected: "Lead" }
 *   select_destination → { selected: "meta_capi" }
 *   mapping_review     → { approved: true, reviews: [...], reason?: "..." }
 *                     OR { approved: false, reason?: "..." }
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

const MOCK_SELECT_SOURCE: ApprovalInterruptPayload = {
  type: "select_source",
  title: "Choose your data source",
  message: "Select the CRM system your customer data lives in.",
  hint: "Don't see your CRM? More sources are coming soon.",
  default_selected: "salesforce",
  options: [
    { id: "salesforce", label: "Salesforce", enabled: true },
    { id: "hubspot", label: "HubSpot", enabled: true },
    { id: "marketo", label: "Marketo", enabled: false },
    { id: "dynamics", label: "MS Dynamics", enabled: false },
  ],
};

const MOCK_SELECT_OBJECT: ApprovalInterruptPayload = {
  type: "select_object",
  title: "Select Salesforce object",
  message: "Which object contains your customer records?",
  requested: "lead",
  options: ["Lead", "Contact", "Account", "Opportunity", "Campaign", "CampaignMember"],
};


const SF_OPPORTUNITY_FIELDS = [
  "Contact.Email", "Contact.Phone", "Amount", "CloseDate",
  "StageName", "StageName=Closed Won", "GCLID", "AnnualRevenue",
  "AccountId", "OwnerId", "LeadSource", "— constant —",
];

// Single destination mapping review
const MOCK_MAPPING_REVIEW_SINGLE: ApprovalInterruptPayload = {
  type: "mapping_review",
  source_object: "Salesforce Opportunity",
  source_fields: SF_OPPORTUNITY_FIELDS,
  destinations: [{ id: "meta_capi", label: "Meta CRM CAPI" }],
  rows: [
    { source_field: "Contact.Email",      cells: { meta_capi: { field: "email (hashed)",  status: "confident"   } } },
    { source_field: "Contact.Phone",      cells: { meta_capi: { field: "phone (hashed)",  status: "confident"   } } },
    { source_field: "StageName=Closed Won", cells: { meta_capi: { field: "event_name",    status: "confident"   } } },
    { source_field: "CloseDate",          cells: { meta_capi: { field: "event_time",      status: "confident"   } } },
    { source_field: "Amount",             cells: { meta_capi: { field: "value",           status: "confident"   } } },
    { source_field: "— constant —", is_constant: true, cells: { meta_capi: { field: "currency", status: "needs_input" } } },
  ],
};

// Multi-destination mapping review
const MOCK_MAPPING_REVIEW_MULTI: ApprovalInterruptPayload = {
  type: "mapping_review",
  source_object: "Salesforce Opportunity",
  source_fields: SF_OPPORTUNITY_FIELDS,
  destinations: [
    { id: "meta_capi",      label: "Meta CRM CAPI"  },
    { id: "google_offline", label: "Google Offline"  },
  ],
  rows: [
    { source_field: "Contact.Email",   cells: { meta_capi: { field: "email (hashed)", status: "confident" }, google_offline: { field: "email (hashed)",   status: "confident"   } } },
    { source_field: "Contact.Phone",   cells: { meta_capi: { field: "phone (hashed)", status: "confident" }, google_offline: { field: "phone (hashed)",   status: "confident"   } } },
    { source_field: "Amount",          cells: { meta_capi: { field: "value",          status: "confident" }, google_offline: { field: "conversion value", status: "confident"   } } },
    { source_field: "CloseDate",       cells: { meta_capi: { field: "event_time",     status: "confident" }, google_offline: { field: "conversion_time",  status: "confident"   } } },
    { source_field: "StageName=Closed Won", cells: { meta_capi: { field: "event_name", status: "confident" }, google_offline: { field: "conversion action — pick", status: "needs_input" } } },
    { source_field: "— constant: USD —",    cells: { meta_capi: { field: "currency",   status: "confident" }, google_offline: { field: "currency",         status: "confident"   } } },
    { source_field: "GCLID (if present)",   cells: { meta_capi: { field: null,         status: "not_required" }, google_offline: { field: "gclid",         status: "needs_input" } } },
  ],
};

// Canonical mapping
const MOCK_CANONICAL_MAPPING: ApprovalInterruptPayload = {
  type: "canonical_mapping",
  canonical_rows: [
    { canonical_field: "Email",            description: "Required · all 5 destinations",                          status: "confident",   source_field: "Contact.Email"         },
    { canonical_field: "Phone",            description: "Recommended · all 5 · lifts match rate",                 status: "confident",   source_field: "Contact.Phone"         },
    { canonical_field: "Conversion value", description: "Required · all 5",                                       status: "confident",   source_field: "Amount"                },
    { canonical_field: "Currency",         description: "Required · all 5",                                       status: "confident",   source_field: "Constant: USD"         },
    { canonical_field: "Conversion time",  description: "Required · all 5",                                       status: "confident",   source_field: "CloseDate"             },
    { canonical_field: "Conversion event", description: "Required · all 5 · Google needs an action match",        status: "needs_input", source_field: "StageName = Closed Won"},
    { canonical_field: "Click ID (GCLID)", description: "Google & Microsoft only · matches the ad click",         status: "needs_input", source_field: "GCLID"                 },
  ],
  info_text: "Signals sends these to Meta, Google, TikTok, Snapchat & LinkedIn automatically — per-platform field names are handled for you.",
};


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
  message:
    "Active connection found for project Acme Prod. You're good to go — the agent will use this connection to fetch your Salesforce schema.",
};

const MOCK_SELECT_CHANNELS: ApprovalInterruptPayload = {
  type: "select_channels",
  title: "Select channels",
  message: "Choose the ad platforms you want to map your data to.",
  min_select: 1,
  options: [
    { id: "meta",     label: "Meta",        enabled: true  },
    { id: "google",   label: "Google",      enabled: true  },
    { id: "tiktok",   label: "TikTok",      enabled: true  },
    { id: "snapchat", label: "Snapchat",    enabled: true  },
    { id: "twitter",  label: "X (Twitter)", enabled: true  },
    { id: "linkedin", label: "LinkedIn",    enabled: true  },
    { id: "bing",     label: "Bing",        enabled: true  },
  ],
};

// Note: message/info_text are sent as regular agent chat messages — NOT in the interrupt payload.
const MOCK_CHECK_CHANNELS_MIXED: ApprovalInterruptPayload = {
  type: "check_channels",
  channels: [
    { id: "meta",   label: "Meta",   status: "connected",     detail: "Acme Business Manager · CRM CAPI ready" },
    { id: "google", label: "Google", status: "not_connected", detail: "No active connection · Offline Conversions" },
  ],
};

const MOCK_CHECK_CHANNELS_EXPIRED: ApprovalInterruptPayload = {
  type: "check_channels",
  channels: [
    { id: "meta",     label: "Meta",     status: "connected", detail: "Acme Business Manager · CRM CAPI ready" },
    { id: "tiktok",   label: "TikTok",   status: "expired",   detail: "Token expired 3 days ago · Events API" },
    { id: "linkedin", label: "LinkedIn", status: "connected", detail: "Acme Corp Page · Conversions API ready" },
  ],
};

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

const MOCK_RESOLVE_FIELDS_ISSUES: ApprovalInterruptPayload = {
  type: "resolve_fields",
  resolve_status: "has_issues",
  destination_label: "Meta",
  source_fields: SF_OPPORTUNITY_FIELDS,
  unresolved_fields: [
    { field: "currency", required: true, suggested_constant: "USD" },
    { field: "conversion_event", required: true },
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
  { label: "5 — Check channels (mixed)",          tag: "check_channels",   payload: MOCK_CHECK_CHANNELS_MIXED    },
  { label: "5 — Check channels (with expired)",   tag: "check_channels",   payload: MOCK_CHECK_CHANNELS_EXPIRED  },
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
