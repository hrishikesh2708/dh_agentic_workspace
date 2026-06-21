"""Seed data — sources, destinations, canonical schema, and destination field mappings.

Revision ID: 0002_seed_data
Revises: 0001_initial_schema
Create Date: 2026-06-21
"""

import json
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text as sql

revision: str = "0002_seed_data"  # pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

SOURCES = [
    {"name": "salesforce", "display_name": "Salesforce", "type": "crm", "is_active": True},
    {"name": "hubspot", "display_name": "HubSpot", "type": "crm", "is_active": False},
    {"name": "zoho_crm", "display_name": "Zoho CRM", "type": "crm", "is_active": False},
    {"name": "leadsquared", "display_name": "LeadSquared", "type": "crm", "is_active": False},
]


# ---------------------------------------------------------------------------
# Destinations
# ---------------------------------------------------------------------------

DESTINATIONS = [
    {
        "name": "meta_capi",
        "display_name": "Meta Conversions API",
        "channel_group": "meta",
        "channel_display_name": "Meta",
        "is_active": True,
        "is_event_destination": True,
        "supported_signal_types": ["offline_conversion"],
        "match_keys": ["person_email", "person_phone_e164"],
        "per_stage_config": {
            # system auto-fills event_name from the funnel stage name
            "event_name": {"field": "event_name", "fill": "stage_name"},
        },
        "required_metadata": [
            {"key": "pixelId", "label": "Meta Pixel ID"},
            {"key": "access_token", "label": "Meta access token", "secret": True},
        ],
    },
    {
        "name": "google_offline_conversions",
        "display_name": "Google Offline Conversions",
        "channel_group": "google",
        "channel_display_name": "Google (offline)",
        "is_active": True,
        "is_event_destination": True,
        "supported_signal_types": ["offline_conversion"],
        "match_keys": ["gclid", "person_email", "person_phone_e164"],
        "per_stage_config": {
            # user sets conversion_action per funnel stage during setup
            "event_name": {"field": "conversion_action", "fill": "user"},
        },
        "required_metadata": None,
    },
    {
        "name": "google_customer_match",
        "display_name": "Google Customer Match",
        "channel_group": "google",
        "channel_display_name": "Google (audience)",
        "is_active": False,
        "is_event_destination": False,
        "supported_signal_types": ["audience"],
        "match_keys": [],  # deliberately empty — to be added post registry refactor
        "per_stage_config": {},
        "required_metadata": [
            {"key": "user_list_resource_name", "label": "Google Customer Match user list"},
        ],
    },
    {
        "name": "tiktok",
        "display_name": "TikTok Events API",
        "channel_group": "tiktok",
        "channel_display_name": "TikTok",
        "is_active": False,
        "is_event_destination": True,
        "supported_signal_types": ["offline_conversion"],
        "match_keys": [],
        "per_stage_config": {},
        "required_metadata": None,
    },
    {
        "name": "snapchat",
        "display_name": "Snapchat Conversions",
        "channel_group": "snapchat",
        "channel_display_name": "Snapchat",
        "is_active": False,
        "is_event_destination": True,
        "supported_signal_types": ["offline_conversion"],
        "match_keys": [],
        "per_stage_config": {},
        "required_metadata": None,
    },
    {
        "name": "linkedin",
        "display_name": "LinkedIn CAPI",
        "channel_group": "linkedin",
        "channel_display_name": "LinkedIn",
        "is_active": False,
        "is_event_destination": True,
        "supported_signal_types": ["offline_conversion"],
        "match_keys": [],
        "per_stage_config": {},
        "required_metadata": None,
    },
]


# ---------------------------------------------------------------------------
# Canonical (Datahash) schema fields
#
# These are the normalized intermediate fields that sit between the source
# (Salesforce) and the destination (Meta, Google, etc.).  Destinations map
# their wire fields to these canonical keys via destination_schema_mapping.
# Hashing, transforms, and destination-specific formatting are all
# destination-level concerns — the canonical layer stores raw/normalized values.
#
# Tuple: (canonical_key, display_label, category, type, hint, is_pii,
#         is_per_stage, allow_constant, accepted_sf_types)
# ---------------------------------------------------------------------------

DATAHASH_SCHEMA = [
    # ── Identity ──────────────────────────────────────────────────────────────
    (
        "person_email",
        "Email Address",
        "identity",
        "string",
        "Normalized email address for identity resolution.",
        True,
        False,
        False,
        ["Email", "Text"],
    ),
    (
        "person_phone_e164",
        "Phone Number (E.164)",
        "identity",
        "string",
        "Phone number in E.164 format.",
        True,
        False,
        False,
        ["Phone", "Text"],
    ),
    (
        "person_first_name",
        "First Name",
        "identity",
        "string",
        "Given name.",
        True,
        False,
        False,
        ["Text", "Name"],
    ),
    (
        "person_last_name",
        "Last Name",
        "identity",
        "string",
        "Family name.",
        True,
        False,
        False,
        ["Text", "Name"],
    ),
    (
        "person_city",
        "City",
        "identity",
        "string",
        "City for address enrichment.",
        False,
        False,
        False,
        ["Text"],
    ),
    (
        "person_region",
        "Region / State",
        "identity",
        "string",
        "Region or state.",
        False,
        False,
        False,
        ["Text", "Picklist"],
    ),
    (
        "person_postal_code",
        "Postal Code",
        "identity",
        "string",
        "Postal or ZIP code.",
        False,
        False,
        False,
        ["Text"],
    ),
    (
        "person_country",
        "Country",
        "identity",
        "string",
        "ISO country name or code.",
        False,
        False,
        False,
        ["Text", "Picklist"],
    ),
    (
        "company_name",
        "Company Name",
        "identity",
        "string",
        "Organization or account name.",
        False,
        False,
        False,
        ["Text"],
    ),
    # ── Event ─────────────────────────────────────────────────────────────────
    (
        "lead_status",
        "Lead Status",
        "event",
        "string",
        "Sales or marketing lifecycle stage.",
        False,
        False,
        False,
        ["Picklist", "Text"],
    ),
    (
        "event_name",
        "Event Name",
        "event",
        "string",
        "Logical conversion or engagement event label.",
        False,
        True,
        False,
        ["Text", "Picklist"],  # is_per_stage = True
    ),
    (
        "event_time",
        "Event Time",
        "event",
        "datetime",
        "When the business event occurred.",
        False,
        True,
        False,
        ["DateTime", "Date"],  # is_per_stage = True
    ),
    # ── Monetary ──────────────────────────────────────────────────────────────
    (
        "revenue_amount",
        "Revenue Amount",
        "monetary",
        "number",
        "Monetary value associated with the event.",
        False,
        False,
        False,
        ["Currency", "Number", "Double"],
    ),
    (
        "currency_code",
        "Currency Code",
        "monetary",
        "string",
        "ISO 4217 currency code.",
        False,
        False,
        True,
        ["Text", "Picklist"],  # allow_constant = True
    ),
    # ── Ad identifier ─────────────────────────────────────────────────────────
    (
        "gclid",
        "Google Click ID",
        "ad_identifier",
        "string",
        "Google Click ID captured at lead creation — attributes offline conversions to the originating ad click.",
        False,
        False,
        False,
        ["Text", "URL"],
    ),
]


# ---------------------------------------------------------------------------
# Destination schema mappings
#
# destination_name   — must match a name in DESTINATIONS
# field_name         — wire field name exactly as in the destination YAML
# canonical_key      — must match a canonical_key in DATAHASH_SCHEMA above
# is_required        — destination treats this field as mandatory
# is_recommended     — destination strongly recommends this field
# source_mode_hint   — "set_at_sync" | "per_stage" | None (= user maps from SF)
# constraints        — e.g. {"hash": "sha256"}, or None
# enum_values        — destination-specific allowed values, or None
# transform_function — name of Python transform to apply before sending, or None
#
# NOTE: set_at_sync fields (event_name, conversion_action) are never shown
# to the user for SF field mapping — they are filled automatically at sync time
# from the funnel stage config or destination metadata.
# ---------------------------------------------------------------------------

DESTINATION_SCHEMA_MAPPINGS = [
    # ── Meta CAPI ─────────────────────────────────────────────────────────────
    {
        "destination_name": "meta_capi",
        "field_name": "event_name",
        "canonical_key": "event_name",
        "is_required": True,
        "is_recommended": False,
        "source_mode_hint": "set_at_sync",
        "constraints": None,
        "enum_values": ["Purchase", "Lead", "CompleteRegistration", "AddToCart"],
        "transform_function": None,
    },
    {
        "destination_name": "meta_capi",
        "field_name": "event_time",
        "canonical_key": "event_time",
        "is_required": True,
        "is_recommended": False,
        "source_mode_hint": None,
        "constraints": None,
        "enum_values": None,
        "transform_function": "convert_to_timestamp",
    },
    {
        "destination_name": "meta_capi",
        "field_name": "em",
        "canonical_key": "person_email",
        "is_required": False,
        "is_recommended": True,
        "source_mode_hint": None,
        "constraints": {"hash": "sha256"},
        "enum_values": None,
        "transform_function": None,
    },
    {
        "destination_name": "meta_capi",
        "field_name": "ph",
        "canonical_key": "person_phone_e164",
        "is_required": False,
        "is_recommended": True,
        "source_mode_hint": None,
        "constraints": {"hash": "sha256"},
        "enum_values": None,
        "transform_function": None,
    },
    {
        "destination_name": "meta_capi",
        "field_name": "value",
        "canonical_key": "revenue_amount",
        "is_required": False,
        "is_recommended": False,
        "source_mode_hint": None,
        "constraints": None,
        "enum_values": None,
        "transform_function": "convert_to_float",
    },
    {
        "destination_name": "meta_capi",
        "field_name": "currency",
        "canonical_key": "currency_code",
        "is_required": False,
        "is_recommended": False,
        "source_mode_hint": None,
        "constraints": None,
        "enum_values": ["USD", "INR", "EUR", "GBP"],
        "transform_function": None,
    },
    # ── Google Offline Conversions ────────────────────────────────────────────
    {
        "destination_name": "google_offline_conversions",
        "field_name": "conversion_action",
        "canonical_key": "event_name",
        "is_required": True,
        "is_recommended": False,
        "source_mode_hint": "set_at_sync",
        "constraints": None,
        "enum_values": None,
        "transform_function": None,
    },
    {
        "destination_name": "google_offline_conversions",
        "field_name": "conversion_date_time",
        "canonical_key": "event_time",
        "is_required": True,
        "is_recommended": False,
        "source_mode_hint": None,
        "constraints": None,
        "enum_values": None,
        "transform_function": "convert_to_google_format",
    },
    {
        "destination_name": "google_offline_conversions",
        "field_name": "gclid",
        "canonical_key": "gclid",
        "is_required": False,
        "is_recommended": True,
        "source_mode_hint": None,
        "constraints": None,
        "enum_values": None,
        "transform_function": None,
    },
    {
        "destination_name": "google_offline_conversions",
        "field_name": "hashed_email",
        "canonical_key": "person_email",
        "is_required": False,
        "is_recommended": True,
        "source_mode_hint": None,
        "constraints": {"hash": "sha256"},
        "enum_values": None,
        "transform_function": None,
    },
    {
        "destination_name": "google_offline_conversions",
        "field_name": "hashed_phone_number",
        "canonical_key": "person_phone_e164",
        "is_required": False,
        "is_recommended": True,
        "source_mode_hint": None,
        "constraints": {"hash": "sha256"},
        "enum_values": None,
        "transform_function": None,
    },
    {
        "destination_name": "google_offline_conversions",
        "field_name": "conversion_value",
        "canonical_key": "revenue_amount",
        "is_required": False,
        "is_recommended": False,
        "source_mode_hint": None,
        "constraints": None,
        "enum_values": None,
        "transform_function": "convert_to_float",
    },
    {
        "destination_name": "google_offline_conversions",
        "field_name": "currency_code",
        "canonical_key": "currency_code",
        "is_required": False,
        "is_recommended": False,
        "source_mode_hint": None,
        "constraints": None,
        "enum_values": ["USD", "INR", "EUR", "GBP"],
        "transform_function": None,
    },
    # ── Google Customer Match ─────────────────────────────────────────────────
    # NOTE: user_list_resource_name is a destination-level setting stored in
    # project_connection_secret (via required_metadata) — not a per-record
    # field mapping, so it is intentionally excluded here.
    {
        "destination_name": "google_customer_match",
        "field_name": "hashed_email",
        "canonical_key": "person_email",
        "is_required": False,
        "is_recommended": True,
        "source_mode_hint": None,
        "constraints": {"hash": "sha256"},
        "enum_values": None,
        "transform_function": None,
    },
    {
        "destination_name": "google_customer_match",
        "field_name": "hashed_phone_number",
        "canonical_key": "person_phone_e164",
        "is_required": False,
        "is_recommended": True,
        "source_mode_hint": None,
        "constraints": {"hash": "sha256"},
        "enum_values": None,
        "transform_function": None,
    },
    {
        "destination_name": "google_customer_match",
        "field_name": "hashed_first_name",
        "canonical_key": "person_first_name",
        "is_required": False,
        "is_recommended": False,
        "source_mode_hint": None,
        "constraints": {"hash": "sha256"},
        "enum_values": None,
        "transform_function": None,
    },
    {
        "destination_name": "google_customer_match",
        "field_name": "hashed_last_name",
        "canonical_key": "person_last_name",
        "is_required": False,
        "is_recommended": False,
        "source_mode_hint": None,
        "constraints": {"hash": "sha256"},
        "enum_values": None,
        "transform_function": None,
    },
    {
        "destination_name": "google_customer_match",
        "field_name": "postal_code",
        "canonical_key": "person_postal_code",
        "is_required": False,
        "is_recommended": False,
        "source_mode_hint": None,
        "constraints": None,
        "enum_values": None,
        "transform_function": None,
    },
    {
        "destination_name": "google_customer_match",
        "field_name": "country_code",
        "canonical_key": "person_country",
        "is_required": False,
        "is_recommended": False,
        "source_mode_hint": None,
        "constraints": None,
        "enum_values": ["US", "IN", "GB", "CA", "AU", "DE", "FR", "ES", "IT", "JP"],
        "transform_function": None,
    },
]


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Sources ─────────────────────────────────────────────────────────────
    conn.execute(
        sql(
            """
            INSERT INTO source (name, display_name, type, is_active, is_deleted)
            VALUES (:name, :display_name, :type, :is_active, false)
            ON CONFLICT (name) DO NOTHING
            """
        ),
        SOURCES,
    )

    # 2. Destinations ─────────────────────────────────────────────────────────
    conn.execute(
        sql(
            """
            INSERT INTO destination (
                name, display_name, channel_group, channel_display_name,
                is_active, is_event_destination,
                supported_signal_types, match_keys, per_stage_config,
                required_metadata, is_deleted
            )
            VALUES (
                :name, :display_name, :channel_group, :channel_display_name,
                :is_active, :is_event_destination,
                :supported_signal_types, :match_keys, :per_stage_config,
                :required_metadata, false
            )
            ON CONFLICT (name) DO NOTHING
            """
        ),
        [
            {
                **d,
                "supported_signal_types": json.dumps(d.get("supported_signal_types", [])),
                "match_keys": json.dumps(d.get("match_keys", [])),
                "per_stage_config": json.dumps(d.get("per_stage_config", {})),
                "required_metadata": json.dumps(d["required_metadata"]) if d.get("required_metadata") else None,
            }
            for d in DESTINATIONS
        ],
    )

    # 3. Canonical schema (datahash_schema) ──────────────────────────────────
    # Tuple index reference:
    # 0: canonical_key  1: display_label  2: category  3: type
    # 4: hint  5: is_pii  6: is_per_stage  7: allow_constant  8: accepted_sf_types
    conn.execute(
        sql(
            """
            INSERT INTO datahash_schema (
                canonical_key, label, display_label, type, category,
                hint, enum_values, accepted_sf_types,
                is_per_stage, allow_constant, is_pii, is_deleted
            )
            VALUES (
                :canonical_key, :canonical_key, :display_label, :type, :category,
                :hint, '[]', :accepted_sf_types,
                :is_per_stage, :allow_constant, :is_pii, false
            )
            ON CONFLICT (canonical_key) DO NOTHING
            """
        ),
        [
            {
                "canonical_key": r[0],
                "display_label": r[1],
                "category": r[2],
                "type": r[3],
                "hint": r[4],
                "is_pii": r[5],
                "is_per_stage": r[6],
                "allow_constant": r[7],
                "accepted_sf_types": json.dumps(r[8]),
            }
            for r in DATAHASH_SCHEMA
        ],
    )

    # 4. Destination schema mappings ──────────────────────────────────────────
    conn.execute(
        sql(
            """
            INSERT INTO destination_schema_mapping (
                destination_id, datahash_schema_id, field_name,
                is_required, is_recommended,
                source_mode_hint, constraints, enum_values,
                transform_function, is_deleted
            )
            SELECT
                d.id,
                ds.id,
                :field_name,
                :is_required,
                :is_recommended,
                :source_mode_hint,
                :constraints,
                :enum_values,
                :transform_function,
                false
            FROM destination d
            JOIN datahash_schema ds ON ds.canonical_key = :canonical_key
            WHERE d.name = :destination_name
            ON CONFLICT (destination_id, field_name) DO NOTHING
            """
        ),
        [
            {
                **m,
                "constraints": json.dumps(m["constraints"]) if m["constraints"] is not None else None,
                "enum_values": json.dumps(m["enum_values"]) if m["enum_values"] is not None else None,
            }
            for m in DESTINATION_SCHEMA_MAPPINGS
        ],
    )


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    conn = op.get_bind()

    dest_names = [d["name"] for d in DESTINATIONS]
    conn.execute(
        sql(
            "DELETE FROM destination_schema_mapping WHERE destination_id IN (SELECT id FROM destination WHERE name = ANY(:names))"
        ),
        {"names": dest_names},
    )
    conn.execute(
        sql("DELETE FROM destination WHERE name = ANY(:names)"),
        {"names": dest_names},
    )

    canonical_keys = [r[0] for r in DATAHASH_SCHEMA]
    conn.execute(
        sql("DELETE FROM datahash_schema WHERE canonical_key = ANY(:keys)"),
        {"keys": canonical_keys},
    )

    source_names = [s["name"] for s in SOURCES]
    conn.execute(
        sql("DELETE FROM source WHERE name = ANY(:names)"),
        {"names": source_names},
    )
