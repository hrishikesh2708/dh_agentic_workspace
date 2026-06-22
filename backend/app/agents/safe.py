"""PII boundary — every SF field value passed to an LLM must flow through here.

Whitelists schema metadata only; masks values with type-shaped tokens.
Call safe_sf_fields() on schema_snapshot before building any LLM prompt.
"""

from __future__ import annotations

import hashlib as _hashlib
from typing import Any

_SF_FIELD_WHITELIST = ("name", "label", "type", "custom", "picklist_values")
_SCHEMA_FIELD_WHITELIST = ("name", "type", "required", "description", "source_mode_hint")

_TYPE_MASK = {
    "email": "<email>",
    "phone": "<e164>",
    "string": "<text>",
    "textarea": "<text>",
    "picklist": "<category>",
    "multipicklist": "<category>",
    "datetime": "<timestamp>",
    "date": "<date>",
    "double": "0.00",
    "currency": "0.00",
    "int": "0",
    "integer": "0",
    "boolean": "<bool>",
    "id": "<id>",
    "reference": "<id>",
    "url": "<url>",
    "percent": "0.00",
    "number": "0.00",
}

_ALLOWED_LLM_KEYS = (
    frozenset(_SF_FIELD_WHITELIST)
    | frozenset(_SCHEMA_FIELD_WHITELIST)
    | frozenset(
        {
            "user_message",
            "objective",
            "current_node",
            "selected_destinations",
            "supported_destinations",
            "available_objects",
            "canonical_fields",
            "destination_fields",
            "required_canonical",
            "sf_fields",
            "sample_shapes",
            "tone",
            "node",
            "stages",
            "labels",
            "source_object",
            "available_stage_values",
            "picklist_fields",
            "trigger_field",
            "suggested_trigger_field",
            "active_destinations",
            "signal_type",
        }
    )
)


def _pick(obj: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    if isinstance(obj, dict):
        return {k: obj.get(k) for k in keys if k in obj}
    return {k: getattr(obj, k) for k in keys if hasattr(obj, k)}


def safe_sf_fields(fields: list[Any]) -> list[dict[str, Any]]:
    """Return Salesforce field metadata only (name/label/type/custom/picklist_values).

    Never include actual field values from SF records.
    """
    return [_pick(f, _SF_FIELD_WHITELIST) for f in fields]


def safe_schema_fields(fields: list[Any]) -> list[dict[str, Any]]:
    """Return canonical/destination field descriptors (no customer data)."""
    return [_pick(f, _SCHEMA_FIELD_WHITELIST) for f in fields]


def mask_sample(field_type: str) -> str:
    """A masked shape token for a value of the given SF field type.

    Returns a type-appropriate placeholder — never the real value.
    """
    return _TYPE_MASK.get((field_type or "").lower(), "<value>")


def assert_no_raw_values(payload: Any, context: str = "") -> None:
    """Defensive guard: ensure a payload passed to an LLM contains only allowed keys.

    Raises ValueError if unexpected keys are found. Use in tests and CI to catch
    PII leaks before they reach the LLM API.
    """

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str) and k not in _ALLOWED_LLM_KEYS:
                    raise ValueError(
                        f"PII boundary violation{f' in {context}' if context else ''}: "
                        f"unexpected key {k!r} in LLM payload."
                    )
                walk(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                walk(v)

    walk(payload)


def is_identity_field(field_name: str) -> bool:
    """True if a Salesforce field name looks like a PII identity field."""
    n = (field_name or "").lower()
    return any(tok in n for tok in ("email", "phone", "mobile", "firstname", "lastname", "name"))


def object_has_identity(field_names: list[str]) -> bool:
    """True if the object's field list includes at least one identity field."""
    return any(is_identity_field(n) for n in field_names)


def compute_schema_fingerprint(schema_snapshot: list[dict]) -> str:
    """SHA-256 of sorted (name, type) pairs from schema_snapshot.

    Use to detect Salesforce schema drift between sessions.
    """
    pairs = sorted((f.get("name", ""), f.get("type", "")) for f in schema_snapshot)
    raw = repr(pairs).encode()
    return _hashlib.sha256(raw).hexdigest()
