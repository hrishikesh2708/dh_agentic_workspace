"""funnel_worker node tools — Phase 3: funnel design.

Flow::

    check_funnel_needed
         │
         ├── funnel not needed (no picklist / user skips)
         │        └── funnel_phase_complete = True → END
         │
         └── funnel needed
                  │
             gather_funnel_stages  ←── HITL: user designs stage table
                  │
             funnel_phase_complete = True → END

The funnel captures the SF picklist field that drives stage transitions
(e.g. Opportunity.StageName) and maps picklist values → stage definitions:
  { stage_order, stage_name, trigger_field, trigger_value,
    time_field, value_field, per_destination }

This data is later written to project_funnel_stage by activation_worker.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from app.agents.orchestrator.state import GlobalAgentState
from app.core.logging import logger
from app.core.metrics import hitl_interruptions_total

FUNNEL_PHASE = "funnel"

# Salesforce field types that can drive a funnel (picklist / status fields)
_PICKLIST_TYPES = {"picklist", "multipicklist"}

# Well-known field names that are almost always the right funnel trigger
_PREFERRED_TRIGGER_FIELDS = {
    "opportunity": "StageName",
    "lead": "Status",
    "contact": "Status",
}


def _agent_event(message: str, status: str = "confirmed") -> AIMessage:
    return AIMessage(
        content=json.dumps(
            {
                "type": "agent_event",
                "status": status,
                "message": message,
                "phase": FUNNEL_PHASE,
            }
        )
    )


def _find_picklist_fields(schema_snapshot: list[dict]) -> list[dict]:
    """Return fields from the SF schema snapshot that are picklist type."""
    return [f for f in schema_snapshot if (f.get("type") or "").lower() in _PICKLIST_TYPES]


# ---------------------------------------------------------------------------
# Node 1 — check_funnel_needed
# ---------------------------------------------------------------------------


async def check_funnel_needed(state: GlobalAgentState) -> dict[str, Any]:
    """Determine if funnel design is relevant for this source object.

    Uses schema_snapshot (loaded by connection_worker) to find picklist fields.
    If no picklists exist, or user already set funnel_enabled=False, skip.

    Emits a HITL interrupt only when picklist fields exist and user hasn't
    yet decided. Payload type: "funnel_prompt" → FunnelPromptCard.
    Resume: { enabled: bool, trigger_field: str | None }
    """
    # Already decided in a previous turn
    if state.funnel_phase_complete:
        return {}

    source_object_lower = (state.source_object or "").lower()
    picklist_fields = _find_picklist_fields(state.schema_snapshot)

    if not picklist_fields:
        # No picklist fields on this object — funnel not possible
        logger.info(
            "funnel_skipped_no_picklist",
            source_object=state.source_object,
        )
        return {
            "funnel_enabled": False,
            "funnel_phase_complete": True,
            "messages": [_agent_event(f"No picklist fields on {state.source_object} — funnel skipped.")],
        }

    # Auto-detect preferred trigger field (e.g. StageName for Opportunity)
    preferred = _PREFERRED_TRIGGER_FIELDS.get(source_object_lower)
    suggested_trigger = (
        preferred if preferred and any(f["name"] == preferred for f in picklist_fields) else picklist_fields[0]["name"]
    )

    picklist_field_options = [{"name": f["name"], "label": f.get("label", f["name"])} for f in picklist_fields]

    payload = {
        "type": "funnel_prompt",
        "source_object": state.source_object,
        "picklist_fields": picklist_field_options,
        "suggested_trigger_field": suggested_trigger,
        "info_text": (
            f"Your {state.source_object} has {len(picklist_fields)} picklist field(s). "
            "Would you like to set up a funnel to track stage progressions?"
        ),
    }

    hitl_interruptions_total.labels(interrupt_type="funnel_prompt").inc()
    response: Any = interrupt(payload)

    enabled = isinstance(response, dict) and response.get("enabled", False)
    trigger_field = (response or {}).get("trigger_field") if enabled else None

    if not enabled:
        return {
            "funnel_enabled": False,
            "funnel_phase_complete": True,
            "messages": [_agent_event("Funnel skipped — continuing without stage tracking.")],
        }

    # Funnel enabled — read picklist values from schema_snapshot.
    # schema_snapshot is freshly populated by connection_worker/gather_object via
    # sf.load_source_schema() → describe_object(), so it already contains all
    # active picklist values. No second API call needed.
    # If values are absent (e.g. SF returned none for this field), the HITL card
    # in gather_funnel_stages renders with an empty list and lets the user type
    # values manually.
    trigger_field = trigger_field or suggested_trigger
    snapshot_by_name = {f["name"]: f for f in state.schema_snapshot}
    trigger_meta = snapshot_by_name.get(trigger_field, {})
    trigger_values: list[str] = trigger_meta.get("picklist_values") or []

    logger.info(
        "funnel_picklist_loaded_from_snapshot",
        source_object=state.source_object,
        trigger_field=trigger_field,
        value_count=len(trigger_values),
    )

    return {
        "funnel_enabled": True,
        "funnel_trigger_field": trigger_field,
        "available_stage_values": trigger_values,
        "messages": [
            _agent_event(
                f"Funnel enabled on {trigger_field}"
                + (
                    f" — {len(trigger_values)} stage values loaded."
                    if trigger_values
                    else " — no values in schema, you can enter them manually."
                ),
                status="in_progress",
            )
        ],
    }


# ---------------------------------------------------------------------------
# Node 2 — gather_funnel_stages  (HITL)
# ---------------------------------------------------------------------------


async def gather_funnel_stages(state: GlobalAgentState) -> dict[str, Any]:
    """HITL interrupt — user maps picklist values → named funnel stages.

    Payload type: "funnel_stages" → FunnelStagesCard
    Resume: {
        stages: [
            {
                stage_name: str,
                trigger_value: str,       # picklist value that triggers this stage
                time_field: str | None,   # SF datetime field for event timestamp
                value_field: str | None,  # SF currency/number field for event value
                per_destination: dict     # e.g. {"meta_capi": {"event_name": "Purchase"}}
            },
            ...
        ]
    }
    """
    # Find datetime and numeric fields from the snapshot for time/value suggestions
    datetime_fields = [
        f["name"] for f in state.schema_snapshot if (f.get("type") or "").lower() in ("datetime", "date")
    ]
    numeric_fields = [
        f["name"]
        for f in state.schema_snapshot
        if (f.get("type") or "").lower() in ("currency", "double", "int", "integer", "number")
    ]

    # Build suggested stage rows from available picklist values
    suggested_stages = [
        {
            "stage_name": val,
            "trigger_value": val,
            "time_field": None,
            "value_field": None,
            "per_destination": {},
        }
        for val in state.available_stage_values
    ]

    payload = {
        "type": "funnel_stages",
        "trigger_field": state.funnel_trigger_field,
        "available_stage_values": state.available_stage_values,
        "suggested_stages": suggested_stages,
        "datetime_fields": datetime_fields,
        "numeric_fields": numeric_fields,
        "active_destinations": state.active_destinations,
        "info_text": (
            f"Map {state.funnel_trigger_field} values to funnel stages. "
            "Each stage will generate a separate signal event."
        ),
    }

    hitl_interruptions_total.labels(interrupt_type="funnel_stages").inc()
    response: Any = interrupt(payload)

    raw_stages = (response or {}).get("stages") or []
    funnel_stages = []
    for i, s in enumerate(raw_stages):
        stage_name = (s.get("stage_name") or "").strip()
        trigger_value = (s.get("trigger_value") or "").strip()
        if not stage_name or not trigger_value:
            continue
        funnel_stages.append(
            {
                "stage_order": i + 1,
                "stage_name": stage_name,
                "trigger_field": state.funnel_trigger_field,
                "trigger_value": trigger_value,
                "time_field": s.get("time_field"),
                "value_field": s.get("value_field"),
                "per_destination": s.get("per_destination") or {},
            }
        )

    return {
        "funnel_stages": funnel_stages,
        "funnel_phase_complete": True,
        "messages": [
            _agent_event(
                f"Funnel configured: {len(funnel_stages)} stage(s) defined.",
                status="confirmed",
            )
        ],
    }
