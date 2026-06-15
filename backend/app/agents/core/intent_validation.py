"""Validation helpers used across the intent_worker and the messages helpers.

Ported from ``crawler_agent/src/graph/intent_validation.py``. Lives in
``core/`` (not ``workers/intent_worker/``) because the message renderer in
``core/messages.py`` also depends on it, and we want to avoid a worker→core
circular import.
"""

from __future__ import annotations

from app.schemas.agent.types import Destinations, Sources


def source_connector_id(source: Sources | None, *, fallback: str = "") -> str:
    """Return the connector slug stored on a :class:`Sources` value."""
    if source is None:
        return fallback
    return source.connector_id


def match_source_label(raw: str | None, sources: list[Sources]) -> Sources | None:
    """Match a parsed display name or slug to a source connector row."""
    needle = normalize_optional_str(raw)
    if not needle:
        return None
    key = needle.lower()
    for source in sources:
        candidates = {source.connector_id.lower(), source.display_name.lower()}
        if source.parent_connector_name:
            candidates.add(source.parent_connector_name.lower())
        if source.parent_connector_id:
            candidates.add(source.parent_connector_id.lower())
        if key in candidates:
            return source
    return None


def destination_platform_id(sub_connector_of: str | None, connector_id: str) -> str:
    """Return the platform-level destination slug (parent when sub-connector, else connector)."""
    return (sub_connector_of or connector_id).strip()


def match_destination_slug(raw: str | None, destinations: list[Destinations]) -> str:
    """Match a parsed display name or slug to a destination platform slug."""
    needle = normalize_optional_str(raw)
    if not needle:
        return ""
    key = needle.lower()
    for destination in destinations:
        platform_id = destination_platform_id(
            destination.sub_connector_of,
            destination.connector_id,
        ).lower()
        candidates = {
            destination.connector_id.lower(),
            destination.display_name.lower(),
            platform_id,
        }
        if destination.parent_connector_name:
            candidates.add(destination.parent_connector_name.lower())
        if destination.parent_connector_id:
            candidates.add(destination.parent_connector_id.lower())
        if key in candidates:
            return platform_id
    return ""


RUN_MODE_CANONICAL_ONLY = "canonical_only"
RUN_MODE_PROJECTION = "projection"


def normalize_optional_str(value: object) -> str | None:
    """Return ``str(value).strip()`` or ``None`` for empty/falsy inputs."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def source_picker_options(sources: list[Sources]) -> list[dict]:
    """Convert connector rows into UI-ready source picker options."""
    return [
        {
            "id": source.connector_id,
            "label": source.display_name,
            "description": "",
            "enabled": True,
        }
        for source in sources
    ]


def enabled_source_ids_from(sources: list[Sources]) -> set[str]:
    """Set of lowercased active source connector slugs."""
    return {source.connector_id.lower() for source in sources}


def enabled_source_ids_from_options(options: list[dict]) -> set[str]:
    """Set of lowercased enabled source IDs from picker options."""
    return {o["id"].lower() for o in options if o.get("enabled", True)}


def first_enabled_source_id_from_options(options: list[dict], *, fallback: str = "salesforce") -> str:
    """First enabled source slug from picker options."""
    enabled = [o for o in options if o.get("enabled", True)]
    return enabled[0]["id"] if enabled else fallback


def source_label_from(source_id: str, sources: list[Sources]) -> str:
    """Resolve a source slug to its display name using connector rows."""
    needle = source_id.lower().strip()
    for source in sources:
        if source.connector_id.lower() == needle:
            return source.display_name
    return source_id.replace("_", " ").title()


def is_valid_source(source: str | None, valid_ids: set[str]) -> bool:
    """True iff ``source`` matches one of ``valid_ids`` (case-insensitive)."""
    normalized = normalize_optional_str(source)
    if not normalized:
        return False
    return normalized.lower() in {source_id.lower() for source_id in valid_ids}


def is_valid_destination(dest: str | None, valid_ids: set[str]) -> bool:
    """True iff ``dest`` matches one of ``valid_ids`` (case-insensitive)."""
    normalized = normalize_optional_str(dest)
    if not normalized:
        return False
    return normalized.lower() in {d.lower() for d in valid_ids}


def compute_run_mode(destination_type: str) -> str:
    """Pick ``canonical_only`` or ``projection`` based on the destination."""
    normalized = normalize_optional_str(destination_type)
    if normalized and normalized.lower() == "canonical":
        return RUN_MODE_CANONICAL_ONLY
    return RUN_MODE_PROJECTION


def canonicalize_object_name(requested: str | None, objects: list[str]) -> str | None:
    """Find ``requested`` in ``objects`` ignoring case; return the canonical form."""
    needle = normalize_optional_str(requested)
    if not needle or not objects:
        return None
    objects_lower = {o.lower(): o for o in objects}
    return objects_lower.get(needle.lower())
