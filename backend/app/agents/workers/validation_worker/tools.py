"""validation_worker node tools — Phase 5: mapping validation.

Flow::

    validate_mappings
         │
         ├── errors exist → show_validation_errors (HITL, user must fix)
         │        └── loops back to validate_mappings after user edits
         │
         └── validation passed → validation_phase_complete=True → END

Validation checks:
- All required canonical keys have at least one approved mapping
- Active destination connections are confirmed
- Funnel stages have required fields (if funnel_enabled)
- No duplicate source_field → canonical_key mappings
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from app.agents.orchestrator.state import GlobalAgentState
from app.core.metrics import hitl_interruptions_total
from app.schemas import MappingStatus

VALIDATION_PHASE = "validation"


def _agent_event(message: str, status: str = "confirmed") -> AIMessage:
    return AIMessage(
        content=json.dumps(
            {
                "type": "agent_event",
                "status": status,
                "message": message,
                "phase": VALIDATION_PHASE,
            }
        )
    )


def _approved_mapped_keys(state: GlobalAgentState) -> set[str]:
    """Canonical keys that have an approved (non-unmatched) mapping."""
    return {
        m.destination_field
        for m in state.mappings
        if m.destination_field
        and m.source_field
        and m.status not in (MappingStatus.unmatched, MappingStatus.not_proposed)
    }


def _run_validation(state: GlobalAgentState) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) from current state.

    Errors block activation. Warnings are shown but don't block.
    """
    errors: list[str] = []
    warnings: list[str] = []

    mapped_keys = _approved_mapped_keys(state)

    # 1. Required canonical keys must all be mapped
    unmapped_required = [
        k for k in state.required_canonical_keys if k not in mapped_keys and k not in state.user_unmapped
    ]
    for key in unmapped_required:
        # Find display label for this key
        label = next(
            (cf.get("field_label", key) for cf in state.canonical_field_details if cf.get("canonical_key") == key),
            key,
        )
        errors.append(f"Required field not mapped: {label} ({key})")

    # 2. Active destinations must all be connected
    for dest in state.active_destinations:
        status = state.channel_statuses.get(dest, "unknown")
        if status not in ("connected", "pending"):
            errors.append(f"Destination not connected: {dest} (status: {status})")

    # 3. Funnel-specific checks
    if state.funnel_enabled:
        if not state.funnel_stages:
            errors.append("Funnel enabled but no stages defined.")
        else:
            for stage in state.funnel_stages:
                if not stage.get("stage_name"):
                    errors.append("A funnel stage is missing a stage_name.")
                if not stage.get("trigger_value"):
                    errors.append(f"Stage {stage.get('stage_name', '?')} has no trigger_value.")

        # Per-stage funnel validation
        if getattr(state, "funnel_enabled", False) and getattr(state, "funnel_stages", None):
            picklist_values = set(getattr(state, "available_stage_values", None) or [])
            seen_trigger_values: set[str] = set()
            for stage in state.funnel_stages:
                name = stage.get("stage_name", "?") if isinstance(stage, dict) else getattr(stage, "stage_name", "?")
                trigger = (
                    stage.get("trigger_value", "") if isinstance(stage, dict) else getattr(stage, "trigger_value", "")
                )

                if not str(name).strip():
                    errors.append("A funnel stage is missing a stage_name.")

                if not str(trigger).strip():
                    errors.append(f"Stage '{name}' has no trigger_value.")
                elif picklist_values and trigger not in picklist_values:
                    warnings.append(f"Stage '{name}' trigger '{trigger}' is not in the known picklist values.")

                if trigger in seen_trigger_values:
                    errors.append(f"Duplicate trigger_value '{trigger}' — each stage needs a unique picklist value.")
                seen_trigger_values.add(trigger)

    # 4. Duplicate source→canonical mappings (warn, not error)
    seen: dict[str, str] = {}
    for m in state.mappings:
        if not m.source_field or not m.destination_field:
            continue
        if m.source_field in seen and seen[m.source_field] != m.destination_field:
            warnings.append(
                f"Source field {m.source_field!r} mapped to multiple canonical keys — "
                f"{seen[m.source_field]!r} and {m.destination_field!r}."
            )
        seen[m.source_field] = m.destination_field

    return errors, warnings


# ---------------------------------------------------------------------------
# Node 1 — validate_mappings
# ---------------------------------------------------------------------------


async def validate_mappings(state: GlobalAgentState) -> dict[str, Any]:
    """Run all validation checks against current state.

    If errors exist, stores them and lets the router send to show_validation_errors.
    If clean, marks validation_passed=True and validation_phase_complete=True.
    """
    errors, warnings = _run_validation(state)

    # Snapshot the mappings at validation time for diff tracking
    validation_snapshot = [m.model_dump() for m in state.mappings]

    if not errors:
        msg = "Validation passed"
        if warnings:
            msg += f" with {len(warnings)} warning(s)"
        return {
            "validation_errors": [],
            "validation_warnings": warnings,
            "validation_passed": True,
            "validation_phase_complete": True,
            "validation_snapshot": validation_snapshot,
            "messages": [_agent_event(msg, status="confirmed")],
        }

    return {
        "validation_errors": errors,
        "validation_warnings": warnings,
        "validation_passed": False,
        "validation_snapshot": validation_snapshot,
        "messages": [
            _agent_event(
                f"Validation found {len(errors)} error(s) — review required.",
                status="error",
            )
        ],
    }


# ---------------------------------------------------------------------------
# Node 2 — show_validation_errors  (HITL)
# ---------------------------------------------------------------------------


async def show_validation_errors(state: GlobalAgentState) -> dict[str, Any]:
    """HITL interrupt — show validation errors and let user decide how to fix.

    Payload type: "validation_errors" → ValidationErrorsCard
    Resume: { action: "edit_mapping" | "skip_errors" | "retry" }
      - edit_mapping: sets pending_action="edit_mapping" → supervisor re-routes to mapping
      - skip_errors: marks validation_passed=True anyway (force-proceed)
      - retry: re-runs validate_mappings
    """
    payload = {
        "type": "validation_errors",
        "errors": state.validation_errors,
        "warnings": state.validation_warnings,
        "info_text": "Fix the issues below or skip to proceed anyway.",
    }

    hitl_interruptions_total.labels(interrupt_type="validation_errors").inc()
    response: Any = interrupt(payload)

    action = (response or {}).get("action", "retry")

    if action == "edit_mapping":
        # Ask supervisor to re-route back to mapping phase
        return {
            "pending_action": "edit_mapping",
            "canonical_mapping_approved": False,
            "mapping_phase_complete": False,
            "mapping_complete_shown": False,
            "validation_errors": [],
            "validation_passed": False,
            "validation_phase_complete": False,
        }

    if action == "skip_errors":
        # Force-proceed despite errors (user explicitly accepts risk)
        return {
            "validation_passed": True,
            "validation_phase_complete": True,
            "messages": [_agent_event("Validation bypassed — proceeding with warnings.", status="warned")],
        }

    # action == "retry" or anything else — clear errors and re-validate
    return {
        "validation_errors": [],
        "validation_passed": False,
    }
