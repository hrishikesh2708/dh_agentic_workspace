"""Agent-wide constants (phase IDs, picker definitions, source options).

Ported verbatim from ``crawler_agent/src/constants.py``.
"""

from __future__ import annotations

INTENT_PHASE = "intent"

INTENT_PICKERS = {
    "source": {
        "title": "Select your source CRM",
        "message": "Choose the CRM you want to map data from.",
    },
    "destination": {
        "title": "Select destination",
        "message": "Where should the mapped data be sent?",
    },
}

# Legacy fallback used only by tests and static helpers outside the DB-backed intent flow.
SOURCE_OPTIONS = [
    {"id": "salesforce", "label": "Salesforce", "enabled": True},
    {"id": "hubspot", "label": "HubSpot", "enabled": False},
    {"id": "marketo", "label": "Marketo", "enabled": False},
    {"id": "postgres", "label": "PostgreSQL", "enabled": False},
]

INTENT_GATHER_STEPS = ("source", "object", "destination")
INTENT_GATHER_STEP_TOTAL = len(INTENT_GATHER_STEPS)


def source_label(source_id: str) -> str:
    """Resolve a source ID to its human-readable label."""
    needle = source_id.lower().strip()
    for option in SOURCE_OPTIONS:
        if option["id"] == needle:
            return str(option["label"])
    return source_id.replace("_", " ").title()
