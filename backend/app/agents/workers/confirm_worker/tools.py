"""confirm_worker node tools — Phase 6: token-gated activation confirmation.

Flow::

    show_confirmation  ←── generates UUID token, shows summary + token (HITL)
         │
    verify_confirmation ←── checks received_confirm_token == pending_confirm_token
         │
         ├── match     → confirmation_phase_complete=True → END
         └── mismatch  → loop back to show_confirmation

Design: The user must type back the UUID token shown in the confirm card.
This prevents accidental activation from mis-clicks or confused users.
Token is stored as pending_confirm_token in state; user's reply goes into
received_confirm_token. The is_confirmed property on GlobalAgentState
evaluates the match.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from app.agents import deps
from app.agents.intent_validation import source_connector_id
from app.agents.orchestrator.state import GlobalAgentState
from app.core.metrics import hitl_interruptions_total
from app.schemas import MappingStatus

CONFIRM_PHASE = "confirm"


def _agent_event(message: str, status: str = "confirmed") -> AIMessage:
    return AIMessage(
        content=json.dumps(
            {
                "type": "agent_event",
                "status": status,
                "message": message,
                "phase": CONFIRM_PHASE,
            }
        )
    )


def _mapped_key_count(state: GlobalAgentState) -> int:
    return sum(
        1
        for m in state.mappings
        if m.destination_field
        and m.source_field
        and m.status not in (MappingStatus.unmatched, MappingStatus.not_proposed)
    )


# ---------------------------------------------------------------------------
# Node 1 — show_confirmation  (HITL)
# ---------------------------------------------------------------------------


async def show_confirmation(state: GlobalAgentState) -> dict[str, Any]:
    """Generate a UUID token and present the activation summary card.

    Payload type: "activation_confirm" → ActivationConfirmCard
    The card shows:
      - Source object + destination list
      - Signal type
      - Mapped field count
      - Funnel stage count (if funnel_enabled)
      - A UUID token the user must type back to confirm

    Resume: { token: str }  — user echoes back the token
    """
    # Generate a fresh token (always — even if one exists, refresh on each show)
    token = str(uuid.uuid4())

    source_id = source_connector_id(state.source) or "salesforce"
    try:
        src_label = await deps.connector_schema.source_label(source_id)
    except Exception:
        src_label = source_id

    dest_labels = []
    for d in state.active_destinations:
        try:
            dest_labels.append(await deps.connector_schema.destination_label(d))
        except Exception:
            dest_labels.append(d)

    mapped_count = _mapped_key_count(state)
    total_count = len(state.required_canonical_keys)

    summary_lines = [
        f"Source: {src_label} — {state.source_object}",
        f"Destinations: {', '.join(dest_labels) or 'none'}",
        f"Signal type: {state.signal_type or 'offline_conversion'}",
        f"Fields mapped: {mapped_count} of {total_count} canonical keys",
    ]
    if state.funnel_enabled and state.funnel_stages:
        summary_lines.append(f"Funnel stages: {len(state.funnel_stages)}")
    if state.deferred_destinations:
        summary_lines.append(f"Deferred (skipped): {', '.join(state.deferred_destinations)}")

    payload = {
        "type": "activation_confirm",
        "token": token,
        "summary": summary_lines,
        "info_text": ("Review the configuration above. Type the confirmation code below to activate."),
        "confirm_label": "Activate",
        "secondary_label": "Go back",
    }

    hitl_interruptions_total.labels(interrupt_type="activation_confirm").inc()
    response: Any = interrupt(payload)

    received = ((response or {}).get("token") or "").strip()

    # Compute config integrity hash
    from app.agents.canonical_map import compute_config_hash

    try:
        mappings_list = [m.model_dump() if hasattr(m, "model_dump") else dict(m) for m in (state.mappings or [])]
        config_hash = compute_config_hash(
            source_object=state.source_object or "",
            mappings=mappings_list,
            funnel_stages=list(state.funnel_stages or []),
            active_destinations=list(state.active_destinations or []),
        )
    except Exception:
        config_hash = None

    return {
        "pending_confirm_token": token,
        "received_confirm_token": received,
        "confirmed_config_hash": config_hash,
        "messages": [_agent_event("Awaiting confirmation token…", status="in_progress")],
    }


# ---------------------------------------------------------------------------
# Node 2 — verify_confirmation
# ---------------------------------------------------------------------------


async def verify_confirmation(state: GlobalAgentState) -> dict[str, Any]:
    """Check that the user echoed back the correct token.

    Uses state.is_confirmed (computed property). On match, sets
    confirmation_phase_complete=True. On mismatch, clears the received token
    so show_confirmation runs again with a new token.
    """
    if state.is_confirmed:
        return {
            "confirmation_phase_complete": True,
            "messages": [_agent_event("Token verified — proceeding to activation.", status="confirmed")],
        }

    # Mismatch — generate new token and re-show
    return {
        "pending_confirm_token": None,
        "received_confirm_token": None,
        "confirmed_config_hash": None,
        "messages": [
            _agent_event(
                "Confirmation code did not match — please try again.",
                status="error",
            )
        ],
    }
