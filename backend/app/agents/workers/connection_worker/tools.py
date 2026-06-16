"""connection_worker node tools — source connection check, object selection, channel checks."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage
from langgraph.types import interrupt
from sqlmodel import Session, select

from app.agents.core import deps
from app.agents.core.intent_validation import (
    canonicalize_object_name,
    enabled_source_ids_from_options,
    first_enabled_source_id_from_options,
    is_valid_source,
    normalize_optional_str,
    source_connector_id,
)
from app.agents.core.messages import intent_gather_event
from app.agents.orchestrator.state import GlobalAgentState
from app.core.logging import logger
from app.core.metrics import hitl_interruptions_total
from app.models import ProjectConnection, ProjectConnectionStatus
from app.services.database import database_service

CONNECTION_PHASE = "connection"

_SUPPORTED_OBJECT_SOURCES = frozenset({"salesforce"})


def _resume_selected(response: Any, *, fallback: str) -> str:
    if not isinstance(response, dict):
        return fallback
    if response.get("approved") is False:
        return fallback
    selected = normalize_optional_str(response.get("selected"))
    return selected or fallback


async def _source_catalog() -> tuple[list[dict], set[str], str]:
    options = await deps.connector_schema.list_picker_source_options()
    valid_ids = enabled_source_ids_from_options(options)
    default = first_enabled_source_id_from_options(options)
    return options, valid_ids, default


async def _coerce_source(source_id: str):
    from app.agents.core.intent_validation import source_label_from
    from app.schemas import Sources

    needle = source_id.lower().strip()
    sources = await deps.source_registry.list_source()
    for source in sources:
        if source.connector_id.lower() == needle:
            return source
    return Sources(
        connector_id=needle,
        connector_type="source",
        display_name=source_label_from(needle, sources),
    )


def _lookup_active_connection(project_id: UUID, connector_slug: str) -> ProjectConnection | None:
    """Return an active ProjectConnection row, or None if not found."""
    with Session(database_service.engine) as db:
        stmt = select(ProjectConnection).where(
            ProjectConnection.project_id == project_id,
            ProjectConnection.connector_slug == connector_slug,
            ProjectConnection.status == ProjectConnectionStatus.active,
        )
        return db.exec(stmt).first()


async def build_check_connection_interrupt(
    *,
    source: str,
    connection_status: str = "connected",
    account_detail: str | None = None,
) -> dict:
    """Build HITL payload for an already-connected source (confirm + proceed)."""
    src_label = await deps.connector_schema.source_label(source)
    payload: dict[str, Any] = {
        "type": "check_connection",
        "phase": CONNECTION_PHASE,
        "source_label": src_label,
        "connection_status": connection_status,
        "message": f"Your {src_label} account is connected. Ready to continue?",
    }
    if account_detail:
        payload["account_detail"] = account_detail
    return payload


async def build_connect_source_interrupt(
    *,
    source: str,
    project_id: str,
) -> dict:
    """Build HITL payload to trigger the OAuth connect screen (not yet connected)."""
    src_label = await deps.connector_schema.source_label(source)
    return {
        "type": "connect_source",
        "phase": CONNECTION_PHASE,
        "source_label": src_label,
        "connector_slug": source,
        "project_id": project_id,
        "message": f"Connect your {src_label} account to continue.",
        "auth_url": None,  # Frontend calls /connections/{slug}/authorize to get this
    }


async def build_select_object_interrupt(
    *,
    source: str,
    objects: list[str],
    recommended: str | None = None,
    confidence: str = "low",
    hint: str | None = None,
    alternatives: list[str] | None = None,
) -> dict:
    """Build HITL payload for selecting the Salesforce object to map."""
    src_label = await deps.connector_schema.source_label(source)

    ordered: list[str] = []
    if recommended and recommended in objects:
        ordered.append(recommended)
    for alt in alternatives or []:
        if alt in objects and alt not in ordered:
            ordered.append(alt)
    for obj in objects:
        if obj not in ordered:
            ordered.append(obj)

    return {
        "type": "select_object",
        "phase": CONNECTION_PHASE,
        "title": f"Select {src_label} object",
        "message": f"Which {src_label} object contains your conversion data?",
        "hint": hint,
        "options": ordered,
        "recommended": recommended,
        "confidence": confidence,
        "default_selected": recommended,
        "requires_confirmation": True,
    }


async def build_unsupported_source_interrupt(*, source: str) -> dict:
    """Build HITL payload when the chosen source is not yet supported."""
    options, _, default = await _source_catalog()
    label = await deps.connector_schema.source_label(source)
    return {
        "type": "select_source",
        "phase": CONNECTION_PHASE,
        "title": "Where is your data?",
        "message": "Which system holds the data you want to send?",
        "hint": f"{label} is not supported yet. Select an available source.",
        "options": options,
        "requested": source,
        "default_selected": default,
    }


async def build_check_channels_interrupt(
    *,
    destinations: list[str],
    channel_statuses: dict[str, str],
) -> dict:
    """Build HITL payload for verifying ad platform channel connections."""
    channels = []
    for dest_id in destinations:
        label = await deps.connector_schema.destination_label(dest_id)
        status = channel_statuses.get(dest_id, "not_connected")
        channels.append({"id": dest_id, "label": label, "status": status})
    return {
        "type": "check_channels",
        "phase": CONNECTION_PHASE,
        "message": "Let's verify your ad platform connections.",
        "channels": channels,
    }


async def _infer_source_object(
    *,
    user_intent: str,
    signal_type: str | None,
    source_object_hint: str | None,
    available_objects: list[str],
) -> dict:
    object_list = "\n".join(f"  - {obj}" for obj in available_objects)
    signal_context = f"Signal type: {signal_type}" if signal_type else "Signal type: unknown"
    hint_context = f'User previously mentioned: "{source_object_hint}"' if source_object_hint else ""

    system = f"""You are helping identify which Salesforce object contains a marketer's conversion data.

## Available objects
{object_list}

## Context
{signal_context}
{hint_context}

## Instructions
Reason from the user's INTENT, not just their words.

## Offline conversion patterns (most common)
- "closed deals", "won opportunities", "revenue", "sales" → Opportunity
- "leads that converted", "converted leads" → Lead
- "customers", "buyers", "purchasers" → Contact
- "campaign responses", "campaign members" → CampaignMember
- "accounts that purchased" → Account

## Output
Return ONLY valid JSON:
{{
  "recommended_object": "<object name from available list>" | null,
  "confidence": "high" | "medium" | "low",
  "reasoning": "<one sentence>",
  "alternatives": ["<other plausible objects>"],
  "hint_for_user": "<one sentence explaining WHY, in plain business terms>"
}}

## Rules
- recommended_object MUST be from the available objects list or null
- alternatives: max 2, from available list
- hint_for_user: no Salesforce jargon"""

    raw: dict = {}
    if deps.openai.client:
        try:
            raw = await deps.openai.chat_json(system, f'User intent: "{user_intent}"')
        except Exception:
            pass

    recommended = raw.get("recommended_object")
    if recommended and recommended not in available_objects:
        canonical = canonicalize_object_name(recommended, available_objects)
        recommended = canonical or None

    return {
        "recommended_object": recommended,
        "confidence": str(raw.get("confidence") or "low"),
        "reasoning": str(raw.get("reasoning") or ""),
        "alternatives": [
            a
            for a in (raw.get("alternatives") or [])
            if isinstance(a, str) and a in available_objects and a != recommended
        ],
        "hint_for_user": str(raw.get("hint_for_user") or ""),
    }


async def check_source_connection(state: GlobalAgentState) -> dict[str, Any]:
    """Connection phase node 1 — verify source CRM auth.

    1. Looks up ProjectConnection scoped by state.project_id + connector_slug.
    2. If active connection found → confirms with user and proceeds.
    3. If not found → sends connect_source interrupt; on return re-checks DB.

    Resume payload:
        Connected path:   {"action": "confirm"}
        Connect path:     {"action": "connected"} after OAuth popup closes
    """
    source_id = source_connector_id(state.source) or "salesforce"
    project_id: UUID | None = state.project_id

    if not project_id:
        # No project context — fall back to confirmed (avoids blocking the flow
        # in dev/test where project_id isn't wired yet).
        logger.warning("check_source_connection_no_project_id", source=source_id)
        src_label = await deps.connector_schema.source_label(source_id)
        return {
            "source_connected": True,
            "messages": [
                AIMessage(
                    content=json.dumps(
                        {
                            "type": "agent_event",
                            "event": "connection_source_verified",
                            "message": f"Source Connected: {src_label}",
                            "phase": CONNECTION_PHASE,
                            "status": "confirmed",
                        }
                    )
                )
            ],
        }

    existing = _lookup_active_connection(project_id, source_id)

    if existing:
        # Already connected — show confirmation card, wait for user to proceed.
        account_detail = (existing.connection_metadata or {}).get("instance_url")
        hitl_interruptions_total.labels(interrupt_type="check_connection").inc()
        _response: Any = interrupt(
            await build_check_connection_interrupt(
                source=source_id,
                connection_status="connected",
                account_detail=account_detail,
            )
        )
        # User confirmed (or we auto-proceed on any truthy response).
    else:
        # Not connected — ask user to go through OAuth.
        hitl_interruptions_total.labels(interrupt_type="connect_source").inc()
        _response = interrupt(
            await build_connect_source_interrupt(
                source=source_id,
                project_id=str(project_id),
            )
        )
        # After OAuth popup closes the frontend resumes with {"action": "connected"}.
        # Re-check DB to confirm the row was actually created.
        existing = _lookup_active_connection(project_id, source_id)
        if not existing:
            logger.warning("check_source_connection_still_missing", source=source_id, project_id=str(project_id))
            # Return without setting source_connected so the router retries.
            return {}

    src_label = await deps.connector_schema.source_label(source_id)
    return {
        "source_connected": True,
        "messages": [
            AIMessage(
                content=json.dumps(
                    {
                        "type": "agent_event",
                        "event": "connection_source_verified",
                        "message": f"Source Connected: {src_label}",
                        "phase": CONNECTION_PHASE,
                        "status": "confirmed",
                    }
                )
            )
        ],
    }


async def gather_object(state: GlobalAgentState) -> dict[str, Any]:
    """Connection phase node 2 — gather source object (moved from intent_worker).

    Uses state.intent_summary as the LLM inference context — much richer than
    last_user_text which at this point would be the confirmation reply ("yes").
    """
    messages: list[Any] = []

    _, valid_source_ids, default_source_id = await _source_catalog()
    current_source = source_connector_id(state.source)
    initial_source = normalize_optional_str(current_source) or default_source_id
    source = initial_source

    if source.lower() not in _SUPPORTED_OBJECT_SOURCES:
        hitl_interruptions_total.labels(interrupt_type="select_source").inc()
        response: Any = interrupt(await build_unsupported_source_interrupt(source=source))
        selected_source = _resume_selected(response, fallback=default_source_id)
        if not is_valid_source(selected_source, valid_source_ids):
            selected_source = default_source_id
        source = selected_source
        if source != initial_source:
            messages.append(await intent_gather_event("source", "confirmed", source_id=source))

    objects: list[str] = list(state.available_objects or [])
    if not objects:
        if not state.project_id:
            raise RuntimeError("project_id required to list Salesforce objects — no env fallback allowed")
        try:
            sf = deps.salesforce_for_project(state.project_id)
            objects = await sf.list_eligible_objects(
                include_standard=True,
                include_custom=True,
            )
        except Exception:
            objects = ["Lead", "Contact", "Account", "Opportunity", "Campaign", "CampaignMember"]

    existing_hint = normalize_optional_str(state.source_object)
    canonical_name = canonicalize_object_name(existing_hint, objects)

    # Use intent_summary (set by confirm_intent) as inference context.
    # Falling back to last_user_text risks using "yes" / "looks good" (the
    # confirmation reply) instead of the original intent message, which gives
    # the LLM no signal to infer the object from.
    from app.agents.core.messages import last_user_text

    user_intent = state.intent_summary or last_user_text(state.messages or [])
    inferred = await _infer_source_object(
        user_intent=user_intent,
        signal_type=state.signal_type,
        source_object_hint=existing_hint,
        available_objects=objects,
    )

    recommended = canonical_name or inferred["recommended_object"]
    hint_text = inferred["hint_for_user"] or None

    if canonical_name:
        display_confidence = "high"
    else:
        display_confidence = inferred["confidence"]

    hitl_interruptions_total.labels(interrupt_type="select_object").inc()
    response = interrupt(
        await build_select_object_interrupt(
            source=source,
            objects=objects,
            recommended=recommended,
            confidence=display_confidence,
            hint=hint_text,
            alternatives=inferred["alternatives"],
        )
    )

    fallback = recommended or (objects[0] if objects else "Lead")
    selected = _resume_selected(response, fallback=fallback)
    if selected not in objects:
        selected = canonicalize_object_name(selected, objects) or fallback

    messages.append(await intent_gather_event("object", "confirmed", source_id=source, source_object=selected))

    result: dict[str, Any] = {
        "source_object": selected,
        "available_objects": objects,
        "messages": messages,
    }
    if source != initial_source:
        result["source"] = await _coerce_source(source)
    return result


async def check_channel_connections(state: GlobalAgentState) -> dict[str, Any]:
    """Connection phase node 3 — verify destination channel connections.

    Mock: all "connected". Real integration is a future task.
    """
    destinations = list(state.destinations or [])
    mock_statuses: dict[str, str] = {d: "connected" for d in destinations}

    hitl_interruptions_total.labels(interrupt_type="check_channels").inc()
    _response: Any = interrupt(
        await build_check_channels_interrupt(
            destinations=destinations,
            channel_statuses=mock_statuses,
        )
    )

    messages: list[Any] = []
    for dest_id in destinations:
        dest_label = await deps.connector_schema.destination_label(dest_id)
        messages.append(
            AIMessage(
                content=json.dumps(
                    {
                        "type": "agent_event",
                        "event": "connection_channel_verified",
                        "message": f"Channel Connected: {dest_label}",
                        "phase": CONNECTION_PHASE,
                        "status": "confirmed",
                    }
                )
            )
        )

    return {
        "channel_statuses": mock_statuses,
        "connection_phase_complete": True,
        "messages": messages,
    }
