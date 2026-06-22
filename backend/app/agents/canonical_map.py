"""Canonical mapping analysis engine.

Pure functions — no DB calls, no async. Takes state fields as arguments.

Key concepts:
- canonical_key: the normalized intermediate field name (e.g. "email", "event_name")
- SF field: Salesforce source field (e.g. "Email", "StageName")
- destination field: ad-platform specific field (e.g. "em" for Meta CAPI)

The canonical layer decouples SF schema from destination schema so that
one SF field can feed multiple destinations without re-mapping.
"""

from __future__ import annotations

import hashlib
from typing import Any

# ---------------------------------------------------------------------------
# Match key rules — required identity fields per destination for matching.
# ---------------------------------------------------------------------------

MATCH_KEY_RULES: dict[str, list[str]] = {
    "meta_capi": ["email"],
    "google_offline": ["email"],
    "google_dm": ["email"],
    "tiktok": ["email"],
    "snapchat": ["email"],
    "linkedin": ["email"],
    "twitter": ["email"],
    "bing": ["email"],
}

# ---------------------------------------------------------------------------
# Canonical field labels and descriptions.
# ---------------------------------------------------------------------------

CANONICAL_LABELS: dict[str, str] = {
    "email": "Email address",
    "phone": "Phone number",
    "first_name": "First name",
    "last_name": "Last name",
    "date_of_birth": "Date of birth",
    "city": "City",
    "state": "State / region",
    "country": "Country",
    "zip": "ZIP / postal code",
    "event_name": "Event name",
    "event_time": "Event timestamp",
    "event_value": "Event value (revenue)",
    "event_currency": "Currency code",
    "order_id": "Order / opportunity ID",
    "stage_name": "Stage name",
    "funnel_stage": "Funnel stage",
    "conversion_action": "Conversion action",
    "customer_id": "Customer / account ID",
    "external_id": "External / CRM ID",
}

CANONICAL_REASONS: dict[str, str] = {
    "email": "Primary identity key — required for user matching across platforms.",
    "phone": "Secondary identity key — improves match rate when email is missing.",
    "event_time": "Required timestamp for deduplication and attribution windows.",
    "event_value": "Revenue value — enables ROAS reporting.",
    "order_id": "Deduplication key — prevents counting the same conversion twice.",
    "event_name": "Tells the platform what type of conversion occurred.",
}

# ---------------------------------------------------------------------------
# Constant-allowed registry.
# ---------------------------------------------------------------------------

CONSTANT_ALLOWED: dict[str, list[str]] = {
    "event_currency": ["USD", "EUR", "GBP", "INR", "AUD", "CAD"],
    "event_name": [],
    "country": [],
    "state": [],
}

# ---------------------------------------------------------------------------
# Per-stage canonical fields.
# ---------------------------------------------------------------------------

PER_STAGE_CANONICAL: list[str] = [
    "event_name",
    "event_time",
    "event_value",
    "funnel_stage",
    "stage_name",
]

# ---------------------------------------------------------------------------
# Related-object identity augmentation.
# ---------------------------------------------------------------------------

RELATED_IDENTITY_OBJECT: dict[str, str] = {"Opportunity": "Contact"}

RELATED_IDENTITY_FIELDS: list[str] = [
    "Email",
    "Phone",
    "MobilePhone",
    "FirstName",
    "LastName",
]

RELATED_IDENTITY_JOIN: dict[str, dict] = {
    "Opportunity": {
        "object": "Contact",
        "via": "OpportunityContactRole",
        "filter": "IsPrimary = true",
    },
}


def relationships_for_config(sf_object: str, canonical_mapping: list[dict]) -> dict:
    """Derive join metadata for any related-object (dotted) source fields."""
    rels: dict[str, dict] = {}
    join = RELATED_IDENTITY_JOIN.get(sf_object)
    for m in canonical_mapping:
        sf = m.get("sf_field", "") or m.get("source_field", "")
        if "." in sf:
            related_obj = sf.split(".", 1)[0]
            if join and join.get("object") == related_obj:
                rels[related_obj] = join
    return rels


# ---------------------------------------------------------------------------
# Coverage analysis
# ---------------------------------------------------------------------------


def required_canonical_keys(destination_types: list[str]) -> list[str]:
    """Union of all canonical keys required by the given destinations."""
    seen: list[str] = []
    seen_set: set[str] = set()
    for dest in destination_types:
        for key in MATCH_KEY_RULES.get(dest, []):
            if key not in seen_set:
                seen.append(key)
                seen_set.add(key)
    for key in ["event_name", "event_time", "event_value", "order_id"]:
        if key not in seen_set:
            seen.append(key)
            seen_set.add(key)
    return seen


def mapped_canonical_keys(mappings: list[dict]) -> set[str]:
    """Set of canonical keys that have at least one approved source-field mapping."""
    return {
        m.get("destination_field") or m.get("canonical_field") or ""
        for m in mappings
        if (m.get("destination_field") or m.get("canonical_field"))
        and m.get("source_field")
        and m.get("status", "") not in ("unmatched", "not_proposed")
    }


def coverage_pct(destination_types: list[str], mappings: list[dict]) -> float:
    """0.0-1.0 fraction of required canonical keys that are mapped."""
    required = required_canonical_keys(destination_types)
    if not required:
        return 1.0
    mapped = mapped_canonical_keys(mappings)
    return sum(1 for k in required if k in mapped) / len(required)


def coverage_hints(
    destination_types: list[str],
    mappings: list[dict],
    schema_snapshot: list[dict],
) -> list[str]:
    """Human-readable hints for the LLM about what still needs mapping."""
    required = required_canonical_keys(destination_types)
    mapped = mapped_canonical_keys(mappings)
    unmapped = [k for k in required if k not in mapped]

    hints: list[str] = []
    for key in unmapped:
        label = CANONICAL_LABELS.get(key, key)
        reason = CANONICAL_REASONS.get(key, "")
        candidate = next(
            (
                f.get("name")
                for f in schema_snapshot
                if key in (f.get("name") or "").lower() or key.replace("_", "") in (f.get("name") or "").lower()
            ),
            None,
        )
        hint = f"'{label}' is not yet mapped"
        if reason:
            hint += f" ({reason})"
        if candidate:
            hint += f". Consider mapping '{candidate}'."
        hints.append(hint)

    return hints


def canonical_needs(
    destination_types: list[str],
    mappings: list[dict],
) -> list[dict]:
    """Per-canonical-key status list for the frontend CanonicalNeedsCard."""
    required = set(required_canonical_keys(destination_types))
    mapped = mapped_canonical_keys(mappings)
    result = []
    for key in required_canonical_keys(destination_types):
        result.append(
            {
                "canonical_key": key,
                "label": CANONICAL_LABELS.get(key, key),
                "reason": CANONICAL_REASONS.get(key, ""),
                "status": "mapped" if key in mapped else "missing",
                "required": key in required,
            }
        )
    return result


# ---------------------------------------------------------------------------
# Per-destination breakdown
# ---------------------------------------------------------------------------


def per_destination_breakdown(
    destination_types: list[str],
    mappings: list[dict],
) -> list[dict]:
    """Per-destination coverage and match-key status for the frontend panel."""
    mapped = mapped_canonical_keys(mappings)
    result = []
    for dest in destination_types:
        required = required_canonical_keys([dest])
        match_keys = MATCH_KEY_RULES.get(dest, [])
        covered = [k for k in match_keys if k in mapped]
        missing = [k for k in match_keys if k not in mapped]
        req_mapped = sum(1 for k in required if k in mapped)
        pct = req_mapped / len(required) if required else 1.0
        result.append(
            {
                "destination": dest,
                "coverage_pct": round(pct * 100, 1),
                "match_keys_covered": covered,
                "match_keys_missing": missing,
                "status": "ready" if not missing else "incomplete",
                "required_count": len(required),
                "mapped_count": req_mapped,
            }
        )
    return result


# ---------------------------------------------------------------------------
# Mapping matrix builder
# ---------------------------------------------------------------------------


def mapping_matrix(
    destination_types: list[str],
    mappings: list[dict],
    schema_snapshot: list[dict],
) -> dict:
    """Build the mapping matrix payload for the MappingMatrixCard."""
    required = required_canonical_keys(destination_types)
    mapped_by_key: dict[str, str] = {}
    for m in mappings:
        key = m.get("destination_field") or m.get("canonical_field") or ""
        sf = m.get("source_field") or ""
        if key and sf and m.get("status") not in ("unmatched", "not_proposed"):
            mapped_by_key[key] = sf

    all_keys = required + [
        k for k in CANONICAL_LABELS if k not in required and k not in ("funnel_stage", "stage_name")
    ]

    source_fields = sorted({f.get("name", "") for f in schema_snapshot if f.get("name")})

    rows = []
    for key in all_keys:
        source_field = mapped_by_key.get(key, "")
        cells: dict[str, dict] = {}
        is_required_for_any = key in required
        for dest in destination_types:
            match_keys = MATCH_KEY_RULES.get(dest, [])
            if key in match_keys:
                status = "mapped" if source_field else "missing"
            elif is_required_for_any:
                status = "mapped" if source_field else "needs_input"
            else:
                status = "mapped" if source_field else "not_required"
            cells[dest] = {"field": source_field or None, "status": status}

        rows.append(
            {
                "canonical_key": key,
                "label": CANONICAL_LABELS.get(key, key),
                "source_field": source_field or None,
                "status": "mapped" if source_field else ("missing" if is_required_for_any else "optional"),
                "cells": cells,
            }
        )

    destinations = [{"id": d, "label": d.replace("_", " ").title()} for d in destination_types]

    return {
        "rows": rows,
        "destinations": destinations,
        "source_fields": source_fields,
    }


# ---------------------------------------------------------------------------
# Mapping lint
# ---------------------------------------------------------------------------


def mapping_lint(
    destination_types: list[str],
    mappings: list[dict],
    funnel_enabled: bool = False,
    funnel_stages: list[dict] | None = None,
) -> list[str]:
    """Deterministic quality warnings."""
    warnings: list[str] = []
    mapped = mapped_canonical_keys(mappings)

    for dest in destination_types:
        for key in MATCH_KEY_RULES.get(dest, []):
            if key not in mapped:
                label = CANONICAL_LABELS.get(key, key)
                warnings.append(f"'{label}' is not mapped — {dest} will have low match rates without it.")

    source_to_keys: dict[str, list[str]] = {}
    for m in mappings:
        sf = m.get("source_field") or ""
        key = m.get("destination_field") or m.get("canonical_field") or ""
        if sf and key:
            source_to_keys.setdefault(sf, []).append(key)
    for sf, keys in source_to_keys.items():
        if len(keys) > 1:
            warnings.append(
                f"'{sf}' is mapped to multiple canonical fields: {', '.join(keys)}. Verify this is intentional."
            )

    if funnel_enabled and funnel_stages:
        for stage in funnel_stages:
            name = stage.get("stage_name", "?")
            per_dest = stage.get("per_destination") or {}
            if not per_dest:
                warnings.append(f"Funnel stage '{name}' has no destination event name configured.")

    return warnings


# ---------------------------------------------------------------------------
# Funnel field fanout
# ---------------------------------------------------------------------------


def funnel_canonical_slots(funnel_stages: list[dict]) -> list[dict]:
    """Expand funnel stages into canonical field slot descriptors."""
    slots: list[dict] = []
    for stage in funnel_stages:
        stage_name = stage.get("stage_name", "")
        stage_order = stage.get("stage_order", 0)
        time_field = stage.get("time_field")
        value_field = stage.get("value_field")
        per_dest = stage.get("per_destination") or {}

        for canonical_key in PER_STAGE_CANONICAL:
            slot: dict[str, Any] = {
                "canonical_key": canonical_key,
                "stage_name": stage_name,
                "stage_order": stage_order,
                "trigger_value": stage.get("trigger_value", ""),
                "trigger_field": stage.get("trigger_field", ""),
            }
            if canonical_key == "event_time" and time_field:
                slot["sf_field_hint"] = time_field
            if canonical_key in ("event_value",) and value_field:
                slot["sf_field_hint"] = value_field
            if canonical_key == "event_name":
                per_dest_names = {d: v.get("event_name", "") for d, v in per_dest.items() if isinstance(v, dict)}
                slot["per_destination_event_names"] = per_dest_names
            slots.append(slot)
    return slots


# ---------------------------------------------------------------------------
# Sample payload builder
# ---------------------------------------------------------------------------


def build_sample_payload(
    destination_type: str,
    mappings: list[dict],
    schema_snapshot: list[dict],
) -> dict[str, Any]:
    """Build a masked sample event payload for a given destination."""
    from app.agents.safe import mask_sample

    type_by_name: dict[str, str] = {f.get("name", ""): f.get("type", "string") for f in schema_snapshot}

    payload: dict[str, Any] = {}
    for m in mappings:
        dest_field = m.get("destination_field") or m.get("canonical_field") or ""
        source_field = m.get("source_field") or ""
        constant_value = m.get("constant_value")

        if not dest_field:
            continue

        if constant_value:
            payload[dest_field] = constant_value
        elif source_field:
            field_type = type_by_name.get(source_field, "string")
            payload[dest_field] = mask_sample(field_type)

    if "meta" in destination_type:
        return {
            "event_name": payload.get("event_name", "<event_name>"),
            "event_time": "<timestamp>",
            "action_source": "system_generated",
            "user_data": {
                k: v
                for k, v in payload.items()
                if k in ("em", "ph", "fn", "ln", "ct", "st", "country", "zp", "external_id")
            },
            "custom_data": {k: v for k, v in payload.items() if k in ("value", "currency", "order_id")},
        }
    elif "google" in destination_type:
        return {
            "conversionAction": payload.get("conversion_action", "<conversion_action>"),
            "conversionDateTime": "<timestamp>",
            "userIdentifiers": [{"hashedEmail": payload.get("email", "<email>")}],
            "conversionValue": payload.get("event_value", "0.00"),
            "currencyCode": payload.get("event_currency", "USD"),
            "orderId": payload.get("order_id", "<id>"),
        }
    return payload


# ---------------------------------------------------------------------------
# Config hash
# ---------------------------------------------------------------------------


def compute_config_hash(
    source_object: str,
    mappings: list[dict],
    funnel_stages: list[dict],
    active_destinations: list[str],
) -> str:
    """SHA-256 of the full configuration snapshot."""
    snapshot = {
        "source_object": source_object,
        "mappings": sorted(
            [
                (m.get("source_field", ""), m.get("destination_field", ""), m.get("constant_value", ""))
                for m in mappings
            ],
        ),
        "funnel_stages": sorted([(s.get("stage_name", ""), s.get("trigger_value", "")) for s in funnel_stages]),
        "active_destinations": sorted(active_destinations),
    }
    raw = repr(snapshot).encode()
    return hashlib.sha256(raw).hexdigest()
