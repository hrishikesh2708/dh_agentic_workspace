"""Schema catalog and canonical field endpoints.

Let the frontend fetch destination metadata and canonical field
requirements without hitting the DB — pure computed responses.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

_DESTINATION_CATALOG = [
    {
        "id": "meta_capi",
        "label": "Meta Conversions API",
        "short_label": "Meta",
        "event_destination": True,
        "per_stage_input": False,
    },
    {
        "id": "google_offline",
        "label": "Google Ads Offline Conversions",
        "short_label": "Google",
        "event_destination": True,
        "per_stage_input": True,
    },
    {
        "id": "google_dm",
        "label": "Google Customer Match",
        "short_label": "Google DM",
        "event_destination": False,
        "per_stage_input": False,
    },
    {
        "id": "tiktok",
        "label": "TikTok Events API",
        "short_label": "TikTok",
        "event_destination": True,
        "per_stage_input": False,
    },
    {
        "id": "snapchat",
        "label": "Snapchat Conversions API",
        "short_label": "Snap",
        "event_destination": True,
        "per_stage_input": False,
    },
    {
        "id": "linkedin",
        "label": "LinkedIn Conversions",
        "short_label": "LinkedIn",
        "event_destination": True,
        "per_stage_input": False,
    },
    {
        "id": "twitter",
        "label": "Twitter / X Conversions",
        "short_label": "Twitter",
        "event_destination": True,
        "per_stage_input": False,
    },
    {
        "id": "bing",
        "label": "Microsoft / Bing Ads",
        "short_label": "Bing",
        "event_destination": True,
        "per_stage_input": False,
    },
]


@router.get("/catalog")
async def get_schema_catalog():
    """Full destination catalog with match key rules and required metadata."""
    from app.agents.canonical_map import MATCH_KEY_RULES, required_canonical_keys, PER_STAGE_CANONICAL

    enriched = []
    for dest in _DESTINATION_CATALOG:
        enriched.append(
            {
                **dest,
                "match_key_rules": MATCH_KEY_RULES.get(dest["id"], []),
                "required_canonical": required_canonical_keys([dest["id"]]),
                "per_stage_canonical": PER_STAGE_CANONICAL if dest.get("per_stage_input") else [],
            }
        )
    return {"destinations": enriched}


@router.get("/canonical")
async def get_canonical_fields():
    """All canonical keys with labels, reasons, and per-destination applicability."""
    from app.agents.canonical_map import CANONICAL_LABELS, CANONICAL_REASONS, CONSTANT_ALLOWED, required_canonical_keys

    all_dests = [d["id"] for d in _DESTINATION_CATALOG]
    fields = []
    for key, label in CANONICAL_LABELS.items():
        applicable = [d for d in all_dests if key in required_canonical_keys([d])]
        fields.append(
            {
                "canonical_key": key,
                "label": label,
                "reason": CANONICAL_REASONS.get(key, ""),
                "applicable_destinations": applicable,
                "constant_allowed": key in CONSTANT_ALLOWED,
                "constant_options": CONSTANT_ALLOWED.get(key, []),
            }
        )
    return {"canonical_fields": fields}
