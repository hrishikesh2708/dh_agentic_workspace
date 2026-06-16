"""mapping_worker node tools — schema fetch, LLM mapping, HITL review, activation."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.types import interrupt
from sqlmodel import col, select

from app.agents import deps
from app.agents.intent_validation import source_connector_id
from app.agents.orchestrator.state import GlobalAgentState
from app.core.metrics import hitl_interruptions_total
from app.models import CanonicalField
from app.models import DestinationFieldMapping
from app.schemas import (
    DestinationField,
    DestinationSchema,
    MappingStatus,
    ProposedMapping,
)

MAPPING_PHASE = "mapping"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _matches_destination(row: DestinationFieldMapping, destinations: list[str]) -> bool:
    """Check if a DestinationFieldMapping row belongs to any of our destinations.

    Handles both "meta_capi" style IDs and split "meta" / "capi" slugs.
    """
    full = f"{row.destination_slug}_{row.sub_destination_slug}".strip("_")
    return row.destination_slug in destinations or row.sub_destination_slug in destinations or full in destinations


def _confidence_to_status(confidence: float, destination_field: str | None) -> str:
    if not destination_field:
        return "missing"
    if confidence >= 0.75:
        return "confident"
    if confidence >= 0.4:
        return "needs_input"
    return "missing"


def _mapped_keys(mappings: list[ProposedMapping]) -> set[str]:
    """Return canonical keys that have a non-empty approved source mapping."""
    return {
        m.destination_field
        for m in mappings
        if m.destination_field
        and m.source_field
        and m.status not in (MappingStatus.unmatched, MappingStatus.not_proposed)
    }


def _agent_event(message: str, status: str = "confirmed") -> AIMessage:
    return AIMessage(
        content=json.dumps(
            {
                "type": "agent_event",
                "status": status,
                "message": message,
                "phase": MAPPING_PHASE,
            }
        )
    )


# ---------------------------------------------------------------------------
# Node 1 — fetch_schemas
# ---------------------------------------------------------------------------


async def fetch_schemas(state: GlobalAgentState) -> dict[str, Any]:
    """Fetch required canonical keys from DB + Salesforce source fields.

    DB queries:
    1. DestinationFieldMapping WHERE is_required=True AND destination matches
    2. CanonicalField for those keys

    Then loads Salesforce object fields (real API or fallback).

    Also builds required_by_labels per canonical key — used in canonical_mapping
    card to show "Required · Meta CAPI, Google DM" instead of raw field hints.
    """
    destinations = list(state.destinations or [])

    async with deps.session_maker() as db:
        # 1. Required destination field → canonical key mappings
        result = await db.execute(
            select(DestinationFieldMapping).where(col(DestinationFieldMapping.is_required).is_(True))
        )
        all_dfm = result.scalars().all()
        relevant = [r for r in all_dfm if _matches_destination(r, destinations)]
        required_canonical_keys = list({r.canonical_key for r in relevant})

        # 2. Canonical field details
        cf_result = await db.execute(
            select(CanonicalField).where(col(CanonicalField.canonical_key).in_(required_canonical_keys))
        )
        canonical_fields = cf_result.scalars().all()

    # Build canonical_key → which destination labels require it
    # Used to display "Required · Meta CAPI, Google DM" in the mapping card
    key_to_dest_slugs: dict[str, list[str]] = {}
    for row in relevant:
        key = row.canonical_key
        # Resolve which state destination this row belongs to
        full = f"{row.destination_slug}_{row.sub_destination_slug}".strip("_")
        matched = next(
            (d for d in destinations if d == full or d == row.destination_slug or d == row.sub_destination_slug),
            full,
        )
        if key not in key_to_dest_slugs:
            key_to_dest_slugs[key] = []
        if matched not in key_to_dest_slugs[key]:
            key_to_dest_slugs[key].append(matched)

    # Resolve destination labels (async — one call per unique dest)
    dest_label_cache: dict[str, str] = {}
    for d in destinations:
        try:
            dest_label_cache[d] = await deps.connector_schema.destination_label(d)
        except Exception:
            dest_label_cache[d] = d

    total_dests = len(destinations)

    canonical_field_details = []
    for cf in canonical_fields:
        required_by_slugs = key_to_dest_slugs.get(cf.canonical_key, [])
        required_by_labels = [dest_label_cache.get(d, d) for d in required_by_slugs]

        # Build the description line shown under field name in canonical_mapping card
        if required_by_labels:
            if len(required_by_labels) == total_dests:
                required_by_text = f"Required · all {total_dests} destinations"
            else:
                required_by_text = f"Required · {', '.join(required_by_labels)}"
        else:
            required_by_text = cf.field_hint or ""

        canonical_field_details.append(
            {
                "canonical_key": cf.canonical_key,
                "field_label": cf.field_label,
                "field_hint": cf.field_hint or "",
                "field_category": str(cf.field_category),
                "is_pii": cf.is_pii,
                "required_by_labels": required_by_labels,
                "required_by_text": required_by_text,  # pre-built for card description
            }
        )

    # 3. Salesforce source schema — use project-scoped client (DB tokens) when available
    sf_client = deps.salesforce_for_project(state.project_id)
    if not state.project_id:
        raise RuntimeError("project_id required for Salesforce schema fetch — no env fallback allowed")
    source_schema = await sf_client.load_source_schema(state.source_object)

    return {
        "source_schema": source_schema,
        "required_canonical_keys": required_canonical_keys,
        "canonical_field_details": canonical_field_details,
        "messages": [
            _agent_event(
                f"Fetching {state.source_object} fields and required canonical keys…",
                status="in_progress",
            )
        ],
    }


# ---------------------------------------------------------------------------
# Node 2 — run_mapping
# ---------------------------------------------------------------------------


def _build_canonical_target_schema(
    canonical_field_details: list[dict],
) -> DestinationSchema:
    """Build a synthetic DestinationSchema from required canonical fields.

    The MapperAgent receives this as its destination schema, mapping
    Salesforce fields → canonical keys.
    """
    fields = [
        DestinationField(
            name=cf["canonical_key"],
            type="string",
            canonical_key=cf["canonical_key"],
            required=True,
            description=(
                f"{cf['field_label']}: {cf['field_hint']}".strip(": ") if cf.get("field_hint") else cf["field_label"]
            ),
        )
        for cf in canonical_field_details
    ]
    return DestinationSchema(
        destination="canonical",
        label="Datahash Canonical",
        description="Required canonical fields across all configured destinations",
        status="active",
        fields=fields,
    )


async def run_mapping(state: GlobalAgentState) -> dict[str, Any]:
    """Run MapperAgent: Salesforce fields → required canonical keys.

    Builds a synthetic canonical DestinationSchema and runs the LLM mapper
    with pgvector example retrieval (destination_type="canonical").
    """
    canonical_schema = _build_canonical_target_schema(state.canonical_field_details)

    # MapperAgent reads state.source_schema + state.destination_schema
    mapper_state = state.model_copy(
        update={
            "destination_schema": canonical_schema,
            "vector_search_destination_type": "canonical",
        }
    )
    result = await deps.mapper.run(mapper_state)
    mappings: list[ProposedMapping] = result.mappings

    return {
        "mappings": mappings,
        "destination_schema": canonical_schema,
        "vector_search_destination_type": "canonical",
        "messages": [
            _agent_event(
                f"Mapping {state.source_object} fields to canonical schema…",
                status="in_progress",
            )
        ],
    }


# ---------------------------------------------------------------------------
# Node 3 — canonical_mapping  (HITL)
# ---------------------------------------------------------------------------


def _build_canonical_rows(
    state: GlobalAgentState,
) -> list[dict]:
    """Build CanonicalMappingRow list from mappings + canonical_field_details.

    Row shape matches frontend CanonicalMappingRow:
      { canonical_field, description, status, source_field }
    canonical_field = field_label (human-readable display text)
    """
    by_canonical: dict[str, ProposedMapping] = {m.destination_field: m for m in state.mappings if m.destination_field}
    rows = []
    for cf in state.canonical_field_details:
        key = cf["canonical_key"]
        m = by_canonical.get(key)
        rows.append(
            {
                "canonical_field": cf["field_label"],
                # Show "Required · Meta, Google" instead of raw field_hint
                "description": cf.get("required_by_text") or cf.get("field_hint") or None,
                "source_field": m.source_field if m else None,
                "status": _confidence_to_status(
                    m.confidence if m else 0.0,
                    m.destination_field if m else None,
                ),
            }
        )
    return rows


async def canonical_mapping_node(state: GlobalAgentState) -> dict[str, Any]:
    """HITL interrupt — user reviews and corrects source field → canonical key mapping.

    Payload type: "canonical_mapping" → CanonicalMappingCard
    Resume:  { approved: bool, rows: CanonicalMappingRow[] }
    """
    rows = _build_canonical_rows(state)
    source_fields = [f.name for f in (state.source_schema.fields if state.source_schema else [])]

    auto_mapped = sum(1 for r in rows if r["status"] == "confident")
    info_text = f"{auto_mapped} of {len(rows)} required fields mapped automatically — review and adjust below."

    payload = {
        "type": "canonical_mapping",
        "canonical_rows": rows,
        "source_fields": source_fields,
        "info_text": info_text,
    }

    hitl_interruptions_total.labels(interrupt_type="canonical_mapping").inc()
    response: Any = interrupt(payload)

    # --- Process response ---
    # Build label → canonical_key lookup for reverse mapping
    label_to_key: dict[str, str] = {cf["field_label"]: cf["canonical_key"] for cf in state.canonical_field_details}

    updated_mappings: list[ProposedMapping] = []
    approved = isinstance(response, dict) and response.get("approved", True)

    if approved:
        for row in response.get("rows") or []:
            label = row.get("canonical_field", "")
            canonical_key = label_to_key.get(label)
            if not canonical_key:
                continue
            source_field = (row.get("source_field") or "").strip()
            updated_mappings.append(
                ProposedMapping(
                    source_field=source_field,
                    destination_field=canonical_key,
                    confidence=0.95 if row.get("status") == "confident" else 0.7,
                    status=(MappingStatus.human_approved if source_field else MappingStatus.unmatched),
                )
            )
    else:
        # User rejected — keep existing mappings, will re-show on next turn
        updated_mappings = list(state.mappings)

    return {
        "mappings": updated_mappings,
        "canonical_mapping_approved": approved,
    }


# ---------------------------------------------------------------------------
# Node 4 — resolve_fields  (conditional HITL)
# ---------------------------------------------------------------------------


async def resolve_fields_node(state: GlobalAgentState) -> dict[str, Any]:
    """HITL interrupt — only fires when required canonical keys are still unmatched.

    Payload type: "resolve_fields" → ResolveFieldsCard
    Resume:  { action: "submit", resolutions: [...] }
         OR  { action: "confirm" }  (when resolve_status was "resolved")
    """
    already_mapped = _mapped_keys(state.mappings)
    unresolved_keys = [k for k in state.required_canonical_keys if k not in already_mapped]

    # Build label lookup
    key_to_cf: dict[str, dict] = {cf["canonical_key"]: cf for cf in state.canonical_field_details}
    label_to_key: dict[str, str] = {cf["field_label"]: cf["canonical_key"] for cf in state.canonical_field_details}

    source_fields = [f.name for f in (state.source_schema.fields if state.source_schema else [])]

    dest_labels = []
    for d in state.destinations or []:
        try:
            label = await deps.connector_schema.destination_label(d)
            dest_labels.append(label)
        except Exception:
            dest_labels.append(d)

    unresolved_fields = []
    for key in unresolved_keys:
        cf = key_to_cf.get(key, {})
        unresolved_fields.append(
            {
                "field": cf.get("field_label", key),
                "required": True,
                # Suggest a constant for known PII fields (e.g. currency → USD)
                "suggested_constant": _suggest_constant(key),
                "suggested_source_field": None,
            }
        )

    payload = {
        "type": "resolve_fields",
        "resolve_status": "has_issues",
        "unresolved_fields": unresolved_fields,
        "source_fields": source_fields,
        "destination_label": ", ".join(dest_labels),
    }

    hitl_interruptions_total.labels(interrupt_type="resolve_fields").inc()
    response: Any = interrupt(payload)

    # --- Process resolutions ---
    mappings = list(state.mappings)

    if isinstance(response, dict) and response.get("action") == "submit":
        for res in response.get("resolutions") or []:
            field_label = res.get("field", "")
            canonical_key = label_to_key.get(field_label)
            if not canonical_key:
                continue

            action = res.get("action")
            if action == "set_constant":
                value = str(res.get("value") or "")
                mappings.append(
                    ProposedMapping(
                        source_field=f"__constant__:{value}",
                        destination_field=canonical_key,
                        confidence=1.0,
                        transformation_needed="constant",
                        status=MappingStatus.human_approved,
                    )
                )
            elif action == "map_field":
                sf = str(res.get("source_field") or "")
                if sf:
                    mappings.append(
                        ProposedMapping(
                            source_field=sf,
                            destination_field=canonical_key,
                            confidence=0.9,
                            status=MappingStatus.human_approved,
                        )
                    )

    return {
        "mappings": mappings,
        "resolve_fields_done": True,
    }


def _suggest_constant(canonical_key: str) -> str | None:
    """Return a sensible default constant for well-known canonical keys."""
    _CONSTANTS: dict[str, str] = {
        "event.monetary.currency": "USD",
        "event.general.action_source": "crm",
    }
    return _CONSTANTS.get(canonical_key)


# ---------------------------------------------------------------------------
# Node 5 — mapping_complete  (informational, no HITL)
# ---------------------------------------------------------------------------


async def mapping_complete(state: GlobalAgentState) -> dict[str, Any]:
    """Emit a summary step card — no interrupt, just an agent_event message."""
    total = len(state.required_canonical_keys)
    mapped = len(_mapped_keys(state.mappings))

    src_label = ""
    try:
        source_id = source_connector_id(state.source) or "salesforce"
        src_label = await deps.connector_schema.source_label(source_id)
    except Exception:
        src_label = "Source"

    message = f"Mapping Complete: {mapped} of {total} required fields mapped ({src_label} {state.source_object})"

    return {
        "mapping_complete_shown": True,
        "messages": [_agent_event(message, status="confirmed")],
    }


# ---------------------------------------------------------------------------
# Node 6 — activate_confirm  (HITL — mock activation)
# ---------------------------------------------------------------------------


async def activate_confirm(state: GlobalAgentState) -> dict[str, Any]:
    """Final HITL — show activation summary and confirm.

    Payload type: "activate_confirm" → ActivateConfirmCard
    Resume:  { action: "activate" }  — mock, no DB writes.
    """
    source_id = source_connector_id(state.source) or "salesforce"
    try:
        src_label = await deps.connector_schema.source_label(source_id)
    except Exception:
        src_label = source_id

    dest_labels = []
    for d in state.destinations or []:
        try:
            dest_labels.append(await deps.connector_schema.destination_label(d))
        except Exception:
            dest_labels.append(d)

    total = len(state.required_canonical_keys)
    mapped = len(_mapped_keys(state.mappings))
    unresolved = total - mapped

    checks = [
        f"✓ {mapped} of {total} required fields mapped",
        f"✓ {src_label} connected",
        f"✓ {len(dest_labels)} destination(s) connected",
    ]
    if unresolved:
        checks.append(f"⚠ {unresolved} field(s) unresolved (optional)")

    payload = {
        "type": "activate_confirm",
        "validation": {
            "title": "Ready to activate",
            "checks": checks,
        },
        "summary_card": {
            "title": f"{src_label} {state.source_object} → {', '.join(dest_labels)}",
            "lines": [
                f"Signal type: {state.signal_type or 'Offline Conversion'}",
                f"{mapped} canonical fields mapped",
            ],
        },
        "confirm_label": "Activate Pipeline",
        "secondary_label": "Review mapping",
    }

    hitl_interruptions_total.labels(interrupt_type="activate_confirm").inc()
    response: Any = interrupt(payload)

    if isinstance(response, dict) and response.get("action") == "activate":
        return {
            "pipeline_activated": True,
            "mapping_phase_complete": True,
            "messages": [_agent_event("Pipeline Activated", status="confirmed")],
        }

    # User chose "Review mapping" — reset back to canonical_mapping
    return {
        "canonical_mapping_approved": False,
        "resolve_fields_done": False,
        "mapping_complete_shown": False,
    }
