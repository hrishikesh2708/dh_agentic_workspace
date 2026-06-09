"""Validation helpers used across the intent_worker and the messages helpers.

Ported from ``crawler_agent/src/graph/intent_validation.py``. Lives in
``core/`` (not ``workers/intent_worker/``) because the message renderer in
``core/messages.py`` also depends on it, and we want to avoid a worker→core
circular import.
"""

from __future__ import annotations

from app.agents.core.constants import SOURCE_OPTIONS

RUN_MODE_CANONICAL_ONLY = "canonical_only"
RUN_MODE_PROJECTION = "projection"


def normalize_optional_str(value: object) -> str | None:
    """Return ``str(value).strip()`` or ``None`` for empty/falsy inputs."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def enabled_source_ids() -> set[str]:
    """Set of lowercased enabled source IDs."""
    return {o["id"].lower() for o in SOURCE_OPTIONS if o.get("enabled", True)}


def enabled_source_options() -> list[dict]:
    """The subset of :data:`SOURCE_OPTIONS` that's currently enabled."""
    return [o for o in SOURCE_OPTIONS if o.get("enabled", True)]


def is_valid_source(source: str | None) -> bool:
    """True iff ``source`` matches an enabled source ID (case-insensitive)."""
    normalized = normalize_optional_str(source)
    if not normalized:
        return False
    return normalized.lower() in enabled_source_ids()


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


def first_enabled_source_id() -> str:
    """First enabled source ID, falling back to ``"salesforce"``."""
    options = enabled_source_options()
    return options[0]["id"] if options else "salesforce"


def source_option_by_id(source_id: str) -> dict | None:
    """Find a source option dict by ID (case-insensitive), or ``None``."""
    needle = source_id.lower().strip()
    for option in SOURCE_OPTIONS:
        if option["id"].lower() == needle:
            return option
    return None
