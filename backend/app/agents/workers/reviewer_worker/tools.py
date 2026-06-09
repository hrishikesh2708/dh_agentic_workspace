"""reviewer_worker pipeline agents + review helpers.

Ported from three crawler_agent files:

- ``src/pipeline/validator.py``          → :class:`ValidatorAgent`
- ``src/pipeline/confidence_scorer.py``  → :class:`ConfidenceScorerAgent`
- ``src/graph/review.py``                → ``expand_mappings_for_review``,
   ``build_mapping_summary`` (module-level helpers)
- ``src/graph/interrupts.py``            → ``build_mapping_review_interrupt``
   (the canonical/projection HITL payload builder)

Import-path-only rewrites; logic is verbatim. The review helpers were
originally written against ``MappingRouterState`` (TypedDict, dict-shaped
mappings); they're adapted to read from :class:`GlobalAgentState` whose
``mappings`` field stores :class:`ProposedMapping` objects.
"""

from __future__ import annotations

from typing import Any

from app.agents.core.agent_config import _AgentSettingsProxy
from app.agents.orchestrator.state import GlobalAgentState
from app.schemas.agent.types import (
    MappingStatus,
    ProposedMapping,
    ValidationStatus,
)


# -----------------------------------------------------------------------------
# Pipeline agents
# -----------------------------------------------------------------------------


class ValidatorAgent:
    """Cross-checks proposed mappings against the source + destination schemas.

    Sets ``validation_status`` / ``validation_notes`` per mapping and appends
    placeholder rows for required destination fields that nothing was mapped
    to. Verbatim port of ``src/pipeline/validator.py``.
    """

    async def run(self, state):
        """Mutate ``state.mappings`` in place with validation outcomes."""
        if not state.destination_schema or not state.source_schema:
            raise ValueError("Validator requires source and destination schemas")

        source_by_name = {f.name: f for f in state.source_schema.fields}
        destination_by_name = {f.name: f for f in state.destination_schema.fields}
        used_destinations: set[str] = set()

        for mapping in state.mappings:
            notes: list[str] = []
            status = ValidationStatus.pass_status

            if not mapping.destination_field:
                mapping.validation_status = ValidationStatus.warn
                mapping.validation_notes = ["No destination field selected"]
                continue

            source_field = source_by_name.get(mapping.source_field)
            destination_field = destination_by_name.get(mapping.destination_field)
            if not source_field or not destination_field:
                mapping.validation_status = ValidationStatus.fail
                mapping.validation_notes = ["Unknown source or destination field"]
                continue

            if destination_field.name in used_destinations:
                notes.append("Duplicate destination mapping")
                status = ValidationStatus.warn
            used_destinations.add(destination_field.name)

            if source_field.type != destination_field.type:
                notes.append(f"Type mismatch: {source_field.type} -> {destination_field.type}")
                status = ValidationStatus.warn

            if destination_field.enum_values and source_field.picklist_values:
                invalid = [v for v in source_field.picklist_values if v not in destination_field.enum_values]
                if invalid:
                    notes.append("Source picklist includes values not present in destination enum")
                    status = ValidationStatus.warn

            mapping.validation_status = status
            mapping.validation_notes = notes

        required_dest_fields = {f.name for f in state.destination_schema.fields if f.required}
        mapped_required = {m.destination_field for m in state.mappings if m.destination_field}
        for field_name in required_dest_fields - mapped_required:
            state.mappings.append(
                ProposedMapping(
                    source_field="",
                    destination_field=field_name,
                    confidence=0.0,
                    reasoning="Required destination field not mapped",
                    validation_status=ValidationStatus.fail,
                    validation_notes=[f"Missing required destination field: {field_name}"],
                )
            )
        return state


class ConfidenceScorerAgent:
    """Adjusts confidence scores per mapping and decides if review is needed.

    Verbatim port of ``src/pipeline/confidence_scorer.py``. Sets
    ``state.has_pending_review = True`` if any mapping landed in
    ``needs_review`` or ``unmatched`` after scoring.
    """

    def __init__(self, settings: _AgentSettingsProxy) -> None:
        """Cache settings (thresholds drive auto-approve vs review)."""
        self.settings = settings

    async def run(self, state):
        """Adjust confidences + set per-mapping ``status`` + ``has_pending_review``."""
        pending_review = False
        for mapping in state.mappings:
            penalty = 0.0
            if mapping.validation_status == ValidationStatus.warn:
                penalty += 0.1
            elif mapping.validation_status == ValidationStatus.fail:
                penalty += 0.25

            adjusted = max(0.0, min(1.0, mapping.confidence - penalty))
            mapping.confidence = adjusted

            if adjusted >= self.settings.auto_approve_threshold:
                mapping.status = MappingStatus.auto_approved
            elif adjusted >= self.settings.review_threshold:
                mapping.status = MappingStatus.needs_review
                pending_review = True
            else:
                mapping.status = MappingStatus.unmatched
                pending_review = True

        state.has_pending_review = pending_review
        return state


# -----------------------------------------------------------------------------
# Review helpers (ported from src/graph/review.py)
# -----------------------------------------------------------------------------

_STATUS_SORT_ORDER = {
    MappingStatus.needs_review.value: 0,
    MappingStatus.unmatched.value: 1,
    MappingStatus.not_proposed.value: 2,
    MappingStatus.auto_approved.value: 3,
    MappingStatus.human_approved.value: 4,
    MappingStatus.human_corrected.value: 5,
}


def _status_sort_key(row: dict) -> tuple[int, str]:
    status = row.get("status") or MappingStatus.not_proposed.value
    return (_STATUS_SORT_ORDER.get(status, 99), row.get("source_field", ""))


def _stub_row(source_field: str) -> dict:
    return {
        "source_field": source_field,
        "destination_field": None,
        "confidence": 0.0,
        "reasoning": "",
        "transformation_needed": None,
        "validation_status": "pass",
        "validation_notes": [],
        "status": MappingStatus.not_proposed.value,
    }


def expand_mappings_for_review(state: GlobalAgentState) -> list[dict]:
    """One row per source schema field, overlaying LLM mapping proposals.

    Returns a list of dicts (the UI-facing shape) so the HITL interrupt
    payload stays JSON-serialisable.
    """
    source = state.source_schema
    mapping_dicts = [m.model_dump() for m in state.mappings]

    if not source:
        return [dict(m) for m in mapping_dicts]

    by_source: dict[str, dict] = {}
    for m in mapping_dicts:
        src = m.get("source_field", "")
        if src and src not in by_source:
            by_source[src] = dict(m)

    expanded: list[dict] = []
    for field in source.fields:
        if field.name in by_source:
            expanded.append(dict(by_source[field.name]))
        else:
            expanded.append(_stub_row(field.name))

    expanded.sort(key=_status_sort_key)
    return expanded


def build_mapping_summary(mappings: list[dict]) -> dict[str, int]:
    """Quick stats for the HITL review payload (total / mapped / needs_review)."""
    total = len(mappings)
    mapped = sum(1 for m in mappings if m.get("destination_field"))
    not_proposed = sum(1 for m in mappings if m.get("status") == MappingStatus.not_proposed.value)
    needs_review = sum(
        1 for m in mappings if m.get("status") in {MappingStatus.needs_review.value, MappingStatus.unmatched.value}
    )
    return {
        "total_source_fields": total,
        "mapped": mapped,
        "not_proposed": not_proposed,
        "needs_review": needs_review,
    }


# -----------------------------------------------------------------------------
# Interrupt payload (ported from src/graph/interrupts.py — mapping_review only)
# -----------------------------------------------------------------------------


def build_mapping_review_interrupt(
    *,
    mapping_kind: str,
    source_object: str,
    destination_type: str,
    mappings: list[dict],
    destination_fields: list[dict],
    mapping_summary: dict[str, int],
) -> dict[str, Any]:
    """Construct the ``mapping_review`` HITL payload (canonical or projection)."""
    return {
        "type": "mapping_review",
        "mapping_kind": mapping_kind,
        "source_object": source_object,
        "destination_type": destination_type,
        "mappings": mappings,
        "destination_fields": destination_fields,
        "mapping_summary": mapping_summary,
    }
