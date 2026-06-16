"""Intent worker node tools — parse, gather, clarify, and confirm mapping intent."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from app.agents import deps
from app.agents.constants import (
    INTENT_PHASE,
)
from app.core.metrics import hitl_interruptions_total
from app.agents.intent_validation import (
    canonicalize_object_name,
    destination_platform_id,
    enabled_source_ids_from_options,
    first_enabled_source_id_from_options,
    is_valid_source,
    match_destination_slug,
    match_source_label,
    normalize_optional_str,
    source_connector_id,
    source_label_from,
)
from app.agents.messages import (
    intent_complete_message,
    intent_gather_event,
    intent_parse_ack_message,
    last_user_text,
)
from app.agents.orchestrator.state import GlobalAgentState
from app.schemas import Sources

_MAPPING_RESET_KEYS: dict[str, Any] = {
    "mappings": [],
    "has_pending_review": False,
    "session_id": None,
    "canonical_session_id": None,
    "source_schema": None,
    "destination_schema": None,
    "vector_search_destination_type": None,
    "canonical_summary_shown": False,
    "available_objects": [],
}


# -----------------------------------------------------------------------------
# Interrupt-payload builders (ported from src/graph/interrupts.py)
# -----------------------------------------------------------------------------


async def _source_catalog() -> tuple[list[dict], set[str], str]:
    """Load source picker options, valid IDs, and default selection from the DB."""
    options = await deps.connector_schema.list_picker_source_options()
    valid_ids = enabled_source_ids_from_options(options)
    default = first_enabled_source_id_from_options(options)
    return options, valid_ids, default


async def build_select_source_interrupt(
    *,
    recommended: str | None = None,
    confidence: str = "low",
    hint: str | None = None,
    is_unsupported: bool = False,
    unsupported_name: str | None = None,
) -> dict:
    """HITL payload for source picker.

    Accepts LLM inference output for pre-fill. User always confirms —
    ``recommended`` only sets the default selection.
    """
    options, _, default = await _source_catalog()
    default_selected = recommended or default

    display_hint = hint
    if is_unsupported and unsupported_name:
        display_hint = f'"{unsupported_name}" isn\'t supported yet. Please select from the available sources below.'

    return {
        "type": "select_source",
        "phase": "intent",
        "title": "Where is your data?",
        "message": "Which system holds the data you want to send?",
        "hint": display_hint,
        "options": options,
        "recommended": recommended,
        "confidence": confidence,
        "default_selected": default_selected,
        "requires_confirmation": True,
    }


def build_select_destinations_interrupt(
    *,
    options: list[dict],
    recommended: list[str] | None = None,
    confidence: str = "low",
    hint: str | None = None,
    unsupported_destinations: list[str] | None = None,
) -> dict:
    """HITL payload for destination multi-select picker.

    Key differences from the old single-select builder:
    - ``recommended`` is a LIST (pre-selected checkboxes)
    - ``multi_select: True`` — UI renders checkboxes, not a radio
    - Shows unsupported destination warning when any were mentioned
    - User always confirms even if all destinations are pre-filled
    """
    valid_options = [o for o in options if o.get("enabled", True)]

    display_hint = hint
    if unsupported_destinations:
        names = ", ".join(unsupported_destinations)
        verb = "is" if len(unsupported_destinations) == 1 else "are"
        note = f"Note: {names} {verb} not supported yet."
        display_hint = f"{hint}\n{note}" if hint else note

    return {
        # "select_channels" matches the frontend HitlApprovalCard switch case
        "type": "select_channels",
        "phase": "intent",
        "title": "Where do you want to send your data?",
        "message": "Select the ad platforms you want to activate.",
        "hint": display_hint,
        "options": valid_options,
        # "default_selected" is what SelectChannelsCard reads for pre-selection
        "default_selected": recommended or [],
        "confidence": confidence,
        "multi_select": True,
        "requires_confirmation": True,
        # "min_select" is what SelectChannelsCard reads (not "min_selections")
        "min_select": 1,
    }


# -----------------------------------------------------------------------------
# Private helpers (ported from src/graph/nodes/intent.py)
# -----------------------------------------------------------------------------


async def _build_parse_system_prompt() -> str:
    sources = await deps.source_registry.list_source()
    destinations = await deps.destination_registry.list_destinations()

    source_lines = "\n".join(f'  "{s.connector_id}"  ({s.display_name})' for s in sources) or "  (none configured)"
    dest_lines = (
        "\n".join(
            f'  "{destination_platform_id(d.sub_connector_of, d.connector_id)}"  ({d.display_name})'
            for d in destinations
        )
        or "  (none configured)"
    )

    return f"""You are an intent parser for Datahash, a marketing-data field-mapping platform.

Parse the user's message and return ONLY valid JSON matching this exact schema:
{{
  "signal_type": "offline_conversion" | "web_conversion" | "lead_conversion" | "custom_audience" | null,
  "signal_type_confidence": "high" | "medium" | "low",
  "source": "<connector_id from the source list>" | null,
  "source_object": "<object name e.g. Lead, Contact, Account>" | null,
  "destinations": ["<connector_id>", ...],
  "ambiguous": true | false,
  "clarification_question": "<short clarifying question>" | null
}}

Available source connector_ids:
{source_lines}

Available destination connector_ids:
{dest_lines}

Signal type definitions:
- "offline_conversion": CRM/offline purchase or conversion events to be sent to an ad platform
- "web_conversion": website pixel or browser events to be sent to an ad platform
- "lead_conversion": lead or form-fill data to be sent to a platform
- "custom_audience": audience segment to be synced to an ad platform

Rules:
- Use connector_id values only — never display names — in "source" and "destinations"
- "destinations" is a list; include all ad platforms the user mentions
- "signal_type_confidence" must always be set ("high" / "medium" / "low")
- Set "ambiguous": true ONLY when signal_type is genuinely impossible to classify even
  with inference — e.g. the user message is completely unrelated to marketing data, or
  equally consistent with two incompatible signal types. Missing source, source_object,
  or destinations are NOT ambiguity — those slots are gathered separately via structured
  pickers. Never set ambiguous=true just because source or destinations are missing.
- "clarification_question" is only set when ambiguous=true, and should ask specifically
  about signal type — not about source or destination (those are handled separately)
- Set unknown / unmentioned fields to null or [] — do not guess"""


def _resume_selected(response: Any, *, fallback: str) -> str:
    if not isinstance(response, dict):
        return fallback
    if response.get("approved") is False:
        return fallback
    selected = normalize_optional_str(response.get("selected"))
    return selected or fallback


async def _coerce_source(source_id: str) -> Sources:
    """Resolve a source slug (from HITL or parsing) to a :class:`Sources` row."""
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


async def _finish_phase_one(
    *,
    source: str,
    source_object: str,
    destination_type: str,
    run_mode: str,
    available_objects: list[str],
    valid_dest_ids: set[str],
    prior_messages: list[Any] | None = None,
) -> list[Any]:
    messages = list(prior_messages or [])
    messages.append(
        await intent_gather_event(
            "destination",
            "confirmed",
            source_id=source,
            source_object=source_object,
            destination_id=destination_type,
        )
    )
    complete = await intent_complete_message(
        source=source,
        source_object=source_object,
        destination_type=destination_type,
        run_mode=run_mode,
        available_objects=available_objects,
        valid_destination_ids=valid_dest_ids,
    )
    if complete:
        messages.append(complete)
    return messages


# -----------------------------------------------------------------------------
# Layer 4 inference helpers
# -----------------------------------------------------------------------------


async def _infer_source(
    *,
    user_intent: str,
    signal_type: str | None,
    raw_source_hint: str | None,
    available_sources: list[dict],
) -> dict:
    """Infer the most likely source system from user intent via LLM.

    Called before the source picker interrupt fires. Even high confidence
    does not bypass the interrupt — it only improves pre-fill quality.
    """
    source_list = "\n".join(f'  - "{s["id"]}": {s["label"]}' for s in available_sources)
    signal_context = f"Signal type: {signal_type}" if signal_type else ""
    hint_context = f'User mentioned: "{raw_source_hint}"' if raw_source_hint else ""

    system = f"""You are identifying which CRM or data source system \
a marketer's conversion data lives in.

## Available sources
{source_list}

## Context
{signal_context}
{hint_context}

## Instructions
Reason from what the user said about their data and workflow.
Match to the closest available source.

## Common patterns
- "Salesforce", "SFDC", "SF", "our CRM" (if only one CRM available) → salesforce
- "HubSpot", "HS" → hubspot
- "our database", "Postgres", "MySQL" → database source
- "spreadsheet", "CSV", "Google Sheets" → file/sheet source
- "warehouse", "BigQuery", "Snowflake" → warehouse source

## Output
Return ONLY valid JSON:
{{
  "recommended_source": "<source id from available list>" | null,
  "confidence": "high" | "medium" | "low",
  "reasoning": "<one sentence>",
  "hint_for_user": "<plain English — why this source fits their goal>",
  "is_unsupported": true | false,
  "unsupported_name": "<what they mentioned if not in list>" | null
}}

## Rules
- recommended_source MUST be from the available list or null
- is_unsupported = true if user clearly named a system not in the list
- high: user named the source explicitly and it matches
- medium: inferred from context, not explicitly named
- low: genuinely unclear"""

    raw: dict = {}
    if deps.openai.client:
        try:
            raw = await deps.openai.chat_json(system, f'User intent: "{user_intent}"')
        except Exception:
            pass

    valid_ids = {s["id"] for s in available_sources}
    recommended = raw.get("recommended_source")
    if recommended and recommended not in valid_ids:
        recommended = None

    return {
        "recommended_source": recommended,
        "confidence": str(raw.get("confidence") or "low"),
        "reasoning": str(raw.get("reasoning") or ""),
        "hint_for_user": str(raw.get("hint_for_user") or ""),
        "is_unsupported": bool(raw.get("is_unsupported", False)),
        "unsupported_name": raw.get("unsupported_name"),
    }


async def _infer_destinations(
    *,
    user_intent: str,
    signal_type: str | None,
    raw_destination_hints: list[str],
    available_destinations: list[dict],
) -> dict:
    """Infer which destinations the user wants from their intent via LLM.

    Returns a list — the platform is multi-destination by design.
    Even if all destinations are confidently inferred, the interrupt
    always fires for user confirmation.
    """
    dest_list = "\n".join(f'  - "{d["id"]}": {d["label"]}' for d in available_destinations)
    signal_context = f"Signal type: {signal_type}" if signal_type else ""
    hints_context = f"User mentioned: {raw_destination_hints}" if raw_destination_hints else ""

    system = f"""You are identifying which ad platforms a marketer \
wants to send conversion data to.

## Available destinations
{dest_list}

## Context
{signal_context}
{hints_context}

## Instructions
- Extract ALL destinations mentioned or clearly implied
- A marketer often runs campaigns on multiple platforms simultaneously
- "all major platforms" is ambiguous — do NOT assume, mark as low confidence

## Common patterns
- "Meta", "Facebook", "FB", "Instagram" → meta_capi
- "Google", "Google Ads", "GDN" → google_ads
- "TikTok", "TT" → tiktok_events
- "Snap", "Snapchat" → snapchat_capi
- "LinkedIn", "LI" → linkedin_capi
- "Pinterest" → pinterest_capi

## Output
Return ONLY valid JSON:
{{
  "recommended_destinations": ["<dest id>"],
  "confidence": "high" | "medium" | "low",
  "reasoning": "<one sentence>",
  "hint_for_user": "<plain English — confirms which platforms were understood>",
  "unsupported_destinations": ["<name>"],
  "missing_destinations": true | false
}}

## Rules
- recommended_destinations: only IDs from the available list
- unsupported_destinations: platforms mentioned but not in the list
- missing_destinations: true if no destination could be inferred at all
- confidence high: user explicitly named platforms that match
- confidence medium: implied but not explicit
- confidence low: vague or contradictory"""

    raw: dict = {}
    if deps.openai.client:
        try:
            raw = await deps.openai.chat_json(system, f'User intent: "{user_intent}"')
        except Exception:
            pass

    valid_ids = {d["id"] for d in available_destinations}
    recommended = [d for d in (raw.get("recommended_destinations") or []) if isinstance(d, str) and d in valid_ids]

    return {
        "recommended_destinations": recommended,
        "confidence": str(raw.get("confidence") or "low"),
        "reasoning": str(raw.get("reasoning") or ""),
        "hint_for_user": str(raw.get("hint_for_user") or ""),
        "unsupported_destinations": [str(u) for u in (raw.get("unsupported_destinations") or [])],
        "missing_destinations": bool(raw.get("missing_destinations", False)),
    }


# -----------------------------------------------------------------------------
# Node functions (ported from src/graph/nodes/intent.py)
# -----------------------------------------------------------------------------


_VALID_SIGNAL_TYPES = frozenset({"offline_conversion", "web_conversion", "lead_conversion", "custom_audience"})


async def parse_initial_intent(state: GlobalAgentState) -> dict[str, Any]:
    """Layer 1 — classify signal type, extract multi-destination intent, detect ambiguity.

    Sets ``intent_phase`` and ``pending_clarification`` in state to drive the router.
    Does NOT touch the gather nodes or ``_route_next``; those still read
    ``state.source``, ``state.source_object``, and ``state.destination_type``
    (the ``destinations[0]`` property) to decide what to gather next.
    """
    user_text = last_user_text(state.messages or [])

    system_prompt = await _build_parse_system_prompt()
    parsed = await deps.openai.chat_json(system_prompt, user_text or "")

    # ---- Extract raw LLM output ------------------------------------------------
    raw_signal_type = normalize_optional_str(parsed.get("signal_type"))
    signal_type_confidence = normalize_optional_str(parsed.get("signal_type_confidence")) or "low"
    raw_source = normalize_optional_str(parsed.get("source"))
    raw_object = normalize_optional_str(parsed.get("source_object"))
    raw_destinations = parsed.get("destinations") or []
    if not isinstance(raw_destinations, list):
        raw_destinations = [raw_destinations] if raw_destinations else []
    ambiguous: bool = bool(parsed.get("ambiguous"))
    clarification_question = normalize_optional_str(parsed.get("clarification_question")) if ambiguous else None

    # ---- Validate against registry --------------------------------------------
    valid_sources = await deps.source_registry.list_source()
    valid_source_ids = {s.connector_id.lower() for s in valid_sources}

    valid_dests = await deps.destination_registry.list_destinations()
    valid_dest_ids = {destination_platform_id(d.sub_connector_of, d.connector_id).lower() for d in valid_dests}

    signal_type = raw_signal_type if raw_signal_type in _VALID_SIGNAL_TYPES else None

    matched_source_id = raw_source.lower() if raw_source and raw_source.lower() in valid_source_ids else ""
    source_object = raw_object or ""

    validated_destinations = [
        d.lower() for d in raw_destinations if isinstance(d, str) and d.lower() in valid_dest_ids
    ]

    # ---- Determine intent_phase ------------------------------------------------
    if ambiguous and clarification_question:
        intent_phase = "clarifying"
    else:
        intent_phase = "gather"

    # ---- Build state update ----------------------------------------------------
    update: dict[str, Any] = {
        **_MAPPING_RESET_KEYS,
        "intent_phase": intent_phase,
        "intent_phase_complete": False,
        "signal_type": signal_type,
        "signal_type_confidence": signal_type_confidence,
        "source_object": source_object,
        "destinations": validated_destinations,
    }

    if matched_source_id:
        update["source"] = await _coerce_source(matched_source_id)

    # ---- Build message ---------------------------------------------------------
    if ambiguous and clarification_question:
        # pending_clarification must be the SLOT NAME (not the question text) so that
        # handle_clarification routes to the correct resolution branch.
        # Ambiguity at parse time always concerns signal_type — source/destinations
        # are never text-clarified here; they go through HITL gather nodes.
        pending_slot = "signal_type"
        already_asked = list(state.clarifications_asked or [])
        if pending_slot not in already_asked:
            already_asked.append(pending_slot)
        update["pending_clarification"] = pending_slot
        update["clarifications_asked"] = already_asked
        update["messages"] = [
            AIMessage(
                content=json.dumps(
                    {
                        "type": "intent_clarify",
                        "event": "clarification_needed",
                        "message": clarification_question,
                        "phase": INTENT_PHASE,
                    }
                )
            )
        ]
    else:
        update["pending_clarification"] = None
        # Resolve labels for the ack message
        src_label_str = ""
        if matched_source_id:
            src_label_str = await deps.connector_schema.source_label(matched_source_id)
        dest_labels = [await deps.connector_schema.destination_label(d) for d in validated_destinations]
        ack = await intent_parse_ack_message(
            user_text,
            signal_type=signal_type,
            source_label_str=src_label_str,
            source_object=source_object,
            destination_labels=dest_labels,
        )
        if ack:
            update["messages"] = [ack]

    return update


async def gather_source(state: GlobalAgentState) -> dict[str, Any]:
    """Layer 4 — gather source CRM with LLM inference.

    Flow:
    1. Run LLM inference from user intent (always — gives hint text even
       when a source was already parsed)
    2. Fire interrupt with inference as pre-fill; confirmation always required
    3. Process confirmed selection

    Never auto-approves — parse_initial_intent may have extracted the source
    but this interrupt is the explicit confirmation step.
    """
    _, valid_source_ids, fallback = await _source_catalog()
    current = source_connector_id(state.source)
    source = normalize_optional_str(current) or ""
    user_intent = last_user_text(state.messages or [])

    source_options = await deps.connector_schema.list_picker_source_options()
    available_sources = [{"id": o["id"], "label": o.get("label", o["id"])} for o in source_options]

    inferred = await _infer_source(
        user_intent=user_intent,
        signal_type=state.signal_type,
        raw_source_hint=source or None,
        available_sources=available_sources,
    )

    # Already-valid source from parse takes priority for pre-selection
    if is_valid_source(source, valid_source_ids):
        recommended = source
        display_confidence = "high"
    else:
        recommended = inferred["recommended_source"]
        display_confidence = inferred["confidence"]

    hitl_interruptions_total.labels(interrupt_type="select_source").inc()
    response: Any = interrupt(
        await build_select_source_interrupt(
            recommended=recommended,
            confidence=display_confidence,
            hint=inferred["hint_for_user"] or None,
            is_unsupported=inferred["is_unsupported"],
            unsupported_name=inferred["unsupported_name"],
        )
    )

    selected = _resume_selected(response, fallback=fallback)
    if not is_valid_source(selected, valid_source_ids):
        selected = fallback

    return {
        "source": await _coerce_source(selected),
        "messages": [
            await intent_gather_event("source", "confirmed", source_id=selected),
        ],
    }


def _resume_selected_list(response: Any, *, fallback: list[str]) -> list[str]:
    """Extract confirmed list from a multi-select interrupt response.

    Mirrors ``_resume_selected`` but for list payloads.
    """
    if not isinstance(response, dict):
        return fallback
    if response.get("approved") is False:
        return fallback
    selected = response.get("selected")
    if isinstance(selected, list) and selected:
        return [str(s) for s in selected]
    if isinstance(selected, str) and selected:
        return [selected]
    return fallback


async def gather_destinations(state: GlobalAgentState) -> dict[str, Any]:
    """Layer 4 — gather destination platforms with LLM inference.

    Multi-select replacement for the old single-destination ``gather_destination``.

    Flow:
    1. Run LLM inference from user intent (merges with any already-parsed destinations)
    2. Fire multi-select interrupt; user confirms or adjusts the pre-selected list
    3. Process confirmed list

    Never auto-approves — parse_initial_intent may have extracted destinations
    but this interrupt is the explicit confirmation step.
    """
    user_intent = last_user_text(state.messages or [])
    destination_options = await deps.connector_schema.list_destination_options()
    valid_ids = await deps.connector_schema.enabled_destination_ids()

    available_destinations = [
        {"id": o["id"], "label": o.get("label", o["id"])} for o in destination_options if o.get("enabled", True)
    ]

    existing = list(state.destinations or [])

    inferred = await _infer_destinations(
        user_intent=user_intent,
        signal_type=state.signal_type,
        raw_destination_hints=existing,
        available_destinations=available_destinations,
    )

    # Merge: already-parsed destinations + inference, deduplicated, valid only
    pre_selected = list(dict.fromkeys(existing + inferred["recommended_destinations"]))
    pre_selected = [d for d in pre_selected if d in valid_ids]

    hitl_interruptions_total.labels(interrupt_type="select_destinations").inc()
    response: Any = interrupt(
        build_select_destinations_interrupt(
            options=destination_options,
            recommended=pre_selected,
            confidence=inferred["confidence"],
            hint=inferred["hint_for_user"] or None,
            unsupported_destinations=inferred["unsupported_destinations"] or None,
        )
    )

    # Process confirmed selection (list response for multi-select)
    first_available = [available_destinations[0]["id"]] if available_destinations else []
    selected_list = _resume_selected_list(response, fallback=pre_selected or first_available)
    confirmed = [d for d in selected_list if d in valid_ids]
    if not confirmed and pre_selected:
        confirmed = [p for p in pre_selected if p in valid_ids]

    # Emit one confirmation event per destination
    current_source = source_connector_id(state.source) or ""
    messages: list[Any] = []
    for dest_id in confirmed:
        messages.append(
            await intent_gather_event(
                "destination",
                "confirmed",
                source_id=current_source,
                destination_id=dest_id,
            )
        )

    return {
        "destinations": confirmed,
        "messages": messages,
    }


# -----------------------------------------------------------------------------
# Layer 2 — clarification loop helpers + handle_clarification node
# -----------------------------------------------------------------------------


async def _build_clarification_resolution_prompt(
    pending_slot: str,
    state: GlobalAgentState,
) -> str:
    """Build a resolution prompt specific to the slot we're trying to clarify."""
    base = """You are resolving a user's reply during a data integration setup conversation.
The user was asked a specific question. Based on their reply, extract the answer.
Return ONLY valid JSON. No explanation outside the JSON."""

    if pending_slot == "signal_type":
        return (
            base
            + """

## What we're resolving
We need to know what TYPE of signal the user wants to send.

## Valid values
- "offline_conversion": CRM deals/sales/purchases → ad platforms to measure post-click revenue
- "web_conversion": website/server-side events via CAPI
- "lead_conversion": form leads / lead gen
- "custom_audience": contact lists for targeting/retargeting

## Output
{
  "resolved": true | false,
  "value": "offline_conversion" | "web_conversion" | "lead_conversion" | "custom_audience" | null,
  "confidence": "high" | "medium" | "low",
  "reasoning": "<why you chose this>",
  "still_ambiguous": "<what is still unclear if resolved=false>"
}

## Examples
- "measure what happens after someone clicks my ad" → offline_conversion, high
- "send my website purchases" → web_conversion, high
- "build an audience from my customer list" → custom_audience, high
- "I want to track conversions" → null, low (too vague — web or offline?)
- "yes measure conversions" → offline_conversion, medium (assuming offline given CRM context)"""
        )

    elif pending_slot == "source":
        sources = await deps.source_registry.list_source()
        source_list = "\n".join(f'  - "{s.connector_id}": {s.display_name}' for s in sources)
        return (
            base
            + f"""

## What we're resolving
We need to know which SOURCE SYSTEM the user's data lives in.

## Available sources
{source_list}

## Output
{{
  "resolved": true | false,
  "value": "<connector_id from list above>" | null,
  "confidence": "high" | "medium" | "low",
  "reasoning": "<why you chose this>",
  "still_ambiguous": "<what is still unclear if resolved=false>"
}}

## Examples
- "our Salesforce" → salesforce, high
- "we use HubSpot CRM" → hubspot, high
- "our CRM" → null, low (which CRM?)
- "the database" → null, low (need more specifics)"""
        )

    elif pending_slot == "destinations":
        destinations = await deps.destination_registry.list_destinations()
        dest_list = "\n".join(
            f'  - "{destination_platform_id(d.sub_connector_of, d.connector_id)}": {d.display_name}'
            for d in destinations
        )
        return (
            base
            + f"""

## What we're resolving
We need to know which AD PLATFORMS the user wants to send data to.
There can be MULTIPLE destinations — extract all that are mentioned.

## Available destinations
{dest_list}

## Output
{{
  "resolved": true | false,
  "value": ["<connector_id>"] | [],
  "confidence": "high" | "medium" | "low",
  "reasoning": "<why you chose these>",
  "still_ambiguous": "<what is still unclear if resolved=false>"
}}

## Examples
- "Meta and Google" → ["meta_capi", "google_ads"], high
- "just Facebook" → ["meta_capi"], high
- "all the major platforms" → [], low (need explicit confirmation)
- "Meta for now" → ["meta_capi"], high"""
        )

    elif pending_slot == "source_object":
        objects = list(
            state.available_objects
            or [
                "Lead",
                "Contact",
                "Account",
                "Opportunity",
                "Campaign",
                "CampaignMember",
            ]
        )
        signal_context = f"Signal type context: {state.signal_type}" if state.signal_type else ""
        return (
            base
            + f"""

## What we're resolving
We need to know which SALESFORCE OBJECT contains the user's conversion data.

## Available objects
{objects}

{signal_context}

## Output
{{
  "resolved": true | false,
  "value": "<object name from list>" | null,
  "confidence": "high" | "medium" | "low",
  "reasoning": "<why you chose this>",
  "still_ambiguous": "<what is still unclear if resolved=false>"
}}

## Examples (for offline_conversion context)
- "closed won deals" → Opportunity, high
- "our won opportunities" → Opportunity, high
- "the leads that converted" → Lead, high
- "customer records" → Contact, medium
- "our data" → null, low (too vague)"""
        )

    else:
        return (
            base
            + f"""

## What we're resolving
Slot: {pending_slot}

## Output
{{
  "resolved": true | false,
  "value": "<extracted value>" | null,
  "confidence": "high" | "medium" | "low",
  "reasoning": "<why>",
  "still_ambiguous": "<what is unclear if resolved=false>"
}}"""
        )


async def _generate_followup_question(
    *,
    pending_slot: str,
    user_reply: str,
    still_ambiguous: str,
    state: GlobalAgentState,
    attempt_count: int,
) -> str:
    """Generate a contextual follow-up when a clarification couldn't be resolved.

    Gets progressively more specific with each failed attempt.
    """
    context_parts: list[str] = []
    if state.signal_type:
        context_parts.append(f"signal type: {state.signal_type}")
    if state.source:
        src_id = source_connector_id(state.source)
        if src_id:
            context_parts.append(f"source: {src_id}")
    if state.destinations:
        context_parts.append(f"destinations: {state.destinations}")

    system = """You are a helpful setup assistant. The user's reply didn't give
enough information to move forward. Generate a SHORT clarifying question.

Rules:
- Maximum 2 sentences
- Be specific — reference what the user said
- On second attempt (attempt >= 2): offer concrete options to pick from
- Never repeat the exact same question
- Never use technical jargon
- Return ONLY JSON: {"question": "<your question>"}"""

    context = (
        f"What we're trying to clarify: {pending_slot}\n"
        f'What the user said: "{user_reply}"\n'
        f"What's still unclear: {still_ambiguous}\n"
        f"What we know so far: {', '.join(context_parts) if context_parts else 'nothing yet'}\n"
        f"Attempt number: {attempt_count}"
    )

    question = ""
    if deps.openai.client:
        try:
            parsed = await deps.openai.chat_json(system, context)
            question = str(parsed.get("question") or "").strip()
        except Exception:
            pass

    if not question:
        fallbacks: dict[str, str] = {
            "signal_type": "Are you looking to measure conversions from your CRM data, or build a targeting audience?",
            "source": "Which CRM or database system holds your customer data?",
            "destinations": "Which ad platforms would you like to send this data to — Meta, Google, TikTok?",
            "source_object": "Which Salesforce object has your conversion data — Opportunity, Lead, or Contact?",
        }
        question = fallbacks.get(
            pending_slot,
            "Could you tell me a bit more about what you're looking to set up?",
        )

    return question


async def _clarification_resolved_ack(
    *,
    pending_slot: str,
    resolved_value: Any,
    reasoning: str,
    state: GlobalAgentState,
) -> AIMessage:
    """Short ack message when a clarification slot is resolved."""
    system = """You are a setup assistant confirming what you just understood.
Write ONE short sentence acknowledging what the user clarified.
Be natural and conversational. Don't say "I have recorded" or "I have noted".
Return ONLY JSON: {"message": "<one sentence>"}"""

    slot_labels: dict[str, str] = {
        "signal_type": f"signal type as {resolved_value}",
        "source": "data source",
        "destinations": f"destinations: {resolved_value}",
        "source_object": f"object: {resolved_value}",
    }
    context = f"Just understood: {slot_labels.get(pending_slot, str(resolved_value))}\nReasoning: {reasoning}"

    message = ""
    if deps.openai.client:
        try:
            parsed = await deps.openai.chat_json(system, context)
            message = str(parsed.get("message") or "").strip()
        except Exception:
            pass

    if not message:
        message = f"Got it, understood your {pending_slot.replace('_', ' ')}."

    payload: dict[str, Any] = {
        "type": "clarification_resolved",
        "event": "slot_confirmed",
        "message": message,
        "phase": "intent",
        "resolved_slot": pending_slot,
        "resolved_value": resolved_value,
    }
    return AIMessage(content=json.dumps(payload))


async def _stay_in_clarify(
    *,
    state: GlobalAgentState,
    pending_slot: str,
    user_text: str,
    still_ambiguous: str,
    attempt_count: int,
    asked_so_far: list[str],
) -> dict[str, Any]:
    """Stay in clarify mode and generate a better follow-up question."""
    question = await _generate_followup_question(
        pending_slot=pending_slot,
        user_reply=user_text,
        still_ambiguous=still_ambiguous,
        state=state,
        attempt_count=attempt_count,
    )
    payload: dict[str, Any] = {
        "type": "clarification_needed",
        "event": "clarification_followup",
        "message": question,
        "phase": "intent",
        "pending_slot": pending_slot,
        "attempt": attempt_count,
    }
    return {
        "intent_phase": "clarifying",
        "pending_clarification": pending_slot,
        "clarifications_asked": asked_so_far + [pending_slot],
        "messages": [AIMessage(content=json.dumps(payload))],
    }


async def handle_clarification(state: GlobalAgentState) -> dict[str, Any]:
    """Layer 2 — handle free-text user replies during the clarification loop.

    Called on every turn while ``intent_phase == "clarifying"``. Tries to resolve
    the pending slot. If resolved, clears pending and sets ``intent_phase =
    "parsing"`` so the router re-runs ``parse_initial_intent`` to find the next
    missing slot. If not resolved, generates a better follow-up and stays in
    clarify mode.

    Never auto-approves — even high-confidence resolutions still go through the
    gather node's HITL interrupt. High confidence just means better pre-fill.
    """
    user_text = last_user_text(state.messages or [])
    pending_slot = state.pending_clarification

    # If there's no pending slot, signal_type is the only slot _route_next can
    # route here without setting pending_clarification first. Treat it as a
    # signal_type clarification rather than silently resetting to "parsing"
    # (which would cause a route_next → handle_clarification loop).
    if not pending_slot:
        asked_so_far = list(state.clarifications_asked or [])
        question = (
            "What type of conversions are you looking to track — "
            "offline purchases from your CRM, website events, or something else?"
        )
        return {
            "pending_clarification": "signal_type",
            "intent_phase": "clarifying",
            "clarifications_asked": asked_so_far + ["signal_type"],
            "messages": [
                AIMessage(
                    content=json.dumps(
                        {
                            "type": "clarification_needed",
                            "event": "clarification_followup",
                            "message": question,
                            "phase": "intent",
                            "pending_slot": "signal_type",
                        }
                    )
                )
            ],
        }

    asked_so_far = list(state.clarifications_asked or [])
    attempt_count = asked_so_far.count(pending_slot) + 1

    # --- Attempt to resolve the slot ------------------------------------------
    resolution_prompt = await _build_clarification_resolution_prompt(pending_slot, state)
    raw = await deps.openai.chat_json(resolution_prompt, user_text)

    resolved: bool = bool(raw.get("resolved", False))
    raw_value: Any = raw.get("value")
    confidence: str = str(raw.get("confidence") or "low")
    reasoning: str = str(raw.get("reasoning") or "")
    still_ambiguous: str = str(raw.get("still_ambiguous") or "")

    # --- Case 1: resolved -------------------------------------------------------
    if resolved and raw_value is not None:
        update: dict[str, Any] = {
            "pending_clarification": None,
            "clarifications_asked": asked_so_far + [pending_slot],
        }

        if pending_slot == "signal_type":
            valid = {"offline_conversion", "web_conversion", "lead_conversion", "custom_audience"}
            if raw_value in valid:
                update["signal_type"] = raw_value
                update["signal_type_confidence"] = confidence
            else:
                return await _stay_in_clarify(
                    state=state,
                    pending_slot=pending_slot,
                    user_text=user_text,
                    still_ambiguous=f'"{raw_value}" is not a recognised signal type',
                    attempt_count=attempt_count,
                    asked_so_far=asked_so_far,
                )

        elif pending_slot == "source":
            valid_sources = await deps.source_registry.list_source()
            matched = match_source_label(raw_value, valid_sources)
            if matched:
                update["source"] = await _coerce_source(matched.connector_id)
            else:
                return await _stay_in_clarify(
                    state=state,
                    pending_slot=pending_slot,
                    user_text=user_text,
                    still_ambiguous=f'"{raw_value}" is not a supported source system',
                    attempt_count=attempt_count,
                    asked_so_far=asked_so_far,
                )

        elif pending_slot == "destinations":
            dest_list = raw_value if isinstance(raw_value, list) else [raw_value]
            valid_dests = await deps.destination_registry.list_destinations()
            validated = [
                slug
                for d in dest_list
                if isinstance(d, str)
                for slug in [match_destination_slug(d, valid_dests)]
                if slug
            ]
            if validated:
                update["destinations"] = validated
            else:
                return await _stay_in_clarify(
                    state=state,
                    pending_slot=pending_slot,
                    user_text=user_text,
                    still_ambiguous="None of the mentioned destinations are supported",
                    attempt_count=attempt_count,
                    asked_so_far=asked_so_far,
                )

        elif pending_slot == "source_object":
            objects = list(state.available_objects or [])
            if objects:
                canonical = canonicalize_object_name(raw_value, objects)
                update["source_object"] = canonical or raw_value
            else:
                update["source_object"] = raw_value

        # Re-run parse so the router can detect the next missing slot
        update["intent_phase"] = "parsing"
        update["messages"] = [
            await _clarification_resolved_ack(
                pending_slot=pending_slot,
                resolved_value=raw_value,
                reasoning=reasoning,
                state=state,
            )
        ]
        return update

    # --- Case 2: not resolved — ask again --------------------------------------
    return await _stay_in_clarify(
        state=state,
        pending_slot=pending_slot,
        user_text=user_text,
        still_ambiguous=still_ambiguous,
        attempt_count=attempt_count,
        asked_so_far=asked_so_far,
    )


# -----------------------------------------------------------------------------
# Layer 5 — intent confirmation helpers + nodes
# -----------------------------------------------------------------------------


_SIGNAL_LABELS: dict[str, str] = {
    "offline_conversion": "offline conversions",
    "web_conversion": "web conversions",
    "lead_conversion": "lead conversions",
    "custom_audience": "custom audience",
}


async def _generate_intent_summary(
    *,
    signal_type: str,
    source: str,
    source_object: str,
    destinations: list[str],
    signal_type_confidence: str | None,
) -> dict:
    """Generate a plain-English summary of the complete intent for user confirmation.

    This is the last step before leaving the intent phase. Makes the full
    picture visible to the user in one coherent place.
    """
    src_label = await deps.connector_schema.source_label(source)
    dest_labels: list[str] = []
    for d in destinations:
        dest_labels.append(await deps.connector_schema.destination_label(d))

    signal_display = _SIGNAL_LABELS.get(signal_type, signal_type)
    if len(dest_labels) <= 2:
        dest_display = " and ".join(dest_labels)
    else:
        dest_display = ", ".join(dest_labels[:-1]) + f" and {dest_labels[-1]}"

    system = """You are confirming a data integration setup with a marketer.
Write a SHORT confirmation summary (2-3 sentences max).

Sentence 1: State what will be set up in plain business terms.
Sentence 2: Ask if this is correct — invite them to correct anything.

Rules:
- No technical jargon (no "connector_id", "CAPI", "slug")
- Use the EXACT labels provided — do not rename them
- Be warm and specific, not generic
- End with a clear yes/no question

Return ONLY JSON:
{"summary": "<2-3 sentence confirmation>", "short_title": "<5 words max>"}"""

    context = (
        f"Signal type: {signal_display}\n"
        f"Source: {src_label}\n"
        f"Object: {source_object}\n"
        f"Destinations: {dest_display}\n"
        f"Confidence: {signal_type_confidence or 'high'}"
    )

    summary = ""
    short_title = ""
    if deps.openai.client:
        try:
            raw = await deps.openai.chat_json(system, context)
            summary = str(raw.get("summary") or "").strip()
            short_title = str(raw.get("short_title") or "").strip()
        except Exception:
            pass

    if not summary:
        summary = (
            f"I'll set up {signal_display} from your {src_label} "
            f"{source_object} records to {dest_display}. "
            f"Does that sound right?"
        )
    if not short_title:
        short_title = f"{src_label} → {dest_display}"

    return {
        "summary": summary,
        "short_title": short_title,
        "src_label": src_label,
        "dest_labels": dest_labels,
        "signal_display": signal_display,
    }


async def _classify_confirmation(
    *,
    user_reply: str,
    current_summary: str,
    signal_type: str | None,
    source: str | None,
    source_object: str | None,
    destinations: list[str],
) -> dict:
    """Classify the user's response to the intent summary.

    Three outcomes:
    - ``confirmed``: user is happy, proceed to connection phase
    - ``partial_correction``: user wants to change something specific
    - ``full_rejection``: user wants to start over

    For partial corrections, extracts exactly what changed.
    """
    system = """You are interpreting a user's response to an integration setup confirmation.

Classify their response and extract any corrections.

## Types
- "confirmed": user agrees with the summary
  Examples: "yes", "that's right", "correct", "looks good", "perfect", "yep"

- "partial_correction": user wants to change ONE OR MORE specific things
  Examples: "just Meta, not Google", "actually use Contacts not Opportunities",
  "add TikTok too", "remove Google", "change source to HubSpot"

- "full_rejection": user wants to start completely over
  Examples: "no that's wrong", "start over", "that's not what I want at all"

## For partial_correction, extract what changed:
- changed_field: "signal_type" | "source" | "source_object" | "destinations"
- change_type: "replace" | "add" | "remove"
- new_value: the new value(s) mentioned
- removed_value: what to remove (for remove/replace)

Return ONLY valid JSON:
{
  "type": "confirmed" | "partial_correction" | "full_rejection",
  "reasoning": "<one sentence>",
  "corrections": [
    {
      "changed_field": "<field>",
      "change_type": "replace" | "add" | "remove",
      "new_value": "<value or list>" | null,
      "removed_value": "<value>" | null
    }
  ]
}

Rules:
- corrections is [] for confirmed and full_rejection
- A user saying "yes but also add TikTok" is partial_correction not confirmed
- Be generous with "confirmed" — minor affirmations count
- corrections can have multiple items"""

    context = (
        f'What was shown to user:\n"{current_summary}"\n\n'
        f"Current setup:\n"
        f"- Signal type: {signal_type}\n"
        f"- Source: {source}\n"
        f"- Object: {source_object}\n"
        f"- Destinations: {destinations}\n\n"
        f'User replied: "{user_reply}"'
    )

    raw: dict = {}
    if deps.openai.client:
        try:
            raw = await deps.openai.chat_json(system, context)
        except Exception:
            pass

    return {
        "type": str(raw.get("type") or "full_rejection"),
        "reasoning": str(raw.get("reasoning") or ""),
        "corrections": raw.get("corrections") or [],
    }


def _apply_corrections(
    corrections: list[dict],
    state: GlobalAgentState,
) -> dict:
    """Apply partial corrections to state.

    Returns only the fields that changed — merged into state by LangGraph.
    Clears corrected slots so the router routes to the right gather node.
    """
    updates: dict[str, Any] = {}

    for correction in corrections:
        field = correction.get("changed_field")
        change_type = correction.get("change_type")
        new_value = correction.get("new_value")
        removed_value = correction.get("removed_value")

        if field == "signal_type":
            updates["signal_type"] = None
            updates["signal_type_confidence"] = None
            updates["pending_clarification"] = "signal_type"
            updates["intent_phase"] = "clarifying"

        elif field == "source":
            updates["source"] = None
            updates["source_object"] = ""
            updates["available_objects"] = []

        elif field == "source_object":
            if change_type == "replace" and new_value:
                updates["source_object"] = str(new_value)
            else:
                updates["source_object"] = ""

        elif field == "destinations":
            current_dests = list(state.destinations or [])

            if change_type == "add" and new_value is not None:
                new_vals = new_value if isinstance(new_value, list) else [new_value]
                updates["destinations"] = list(dict.fromkeys(current_dests + new_vals))

            elif change_type == "remove" and removed_value is not None:
                remove_vals = removed_value if isinstance(removed_value, list) else [removed_value]
                updates["destinations"] = [d for d in current_dests if d not in remove_vals]

            elif change_type == "replace":
                new_vals = new_value if isinstance(new_value, list) else [new_value] if new_value else []
                updates["destinations"] = new_vals

    # If no explicit phase set above → reset to parsing so router finds empty slots
    if "intent_phase" not in updates:
        updates["intent_phase"] = "parsing"

    # Clear summary — will be regenerated after corrections resolved
    updates["intent_summary"] = None

    return updates


async def confirm_intent(state: GlobalAgentState) -> dict[str, Any]:
    """Layer 5 — generate intent summary and present to user for confirmation.

    All slots are filled at this point. This node:
    1. Generates a plain-English summary via LLM
    2. Stores summary in ``intent_summary`` for ``handle_confirmation``
    3. Sets ``intent_phase = "confirming"``
    4. Emits an ``intent_summary`` event message

    The response is handled by ``handle_confirmation`` on the next turn.
    """
    source_id = source_connector_id(state.source) or ""

    summary_data = await _generate_intent_summary(
        signal_type=state.signal_type or "offline_conversion",
        source=source_id,
        source_object=state.source_object or "",
        destinations=state.destinations or [],
        signal_type_confidence=state.signal_type_confidence,
    )

    details: dict[str, Any] = {
        "signal_type": state.signal_type,
        "signal_display": summary_data["signal_display"],
        "source": source_id,
        "source_label": summary_data["src_label"],
        "source_object": state.source_object,
        "destinations": state.destinations,
        "destination_labels": summary_data["dest_labels"],
    }

    return {
        "intent_summary": summary_data["summary"],
        "intent_phase": "confirming",
        "messages": [
            AIMessage(
                content=json.dumps(
                    {
                        "type": "intent_summary",
                        "event": "intent_confirm_shown",
                        "message": summary_data["summary"],
                        "phase": "intent",
                        "title": summary_data["short_title"],
                        "details": details,
                        "actions": [
                            {"id": "confirm", "label": "Yes, that's right", "style": "primary"},
                            {"id": "correct", "label": "I need to change something", "style": "secondary"},
                        ],
                        "requires_confirmation": True,
                    }
                )
            )
        ],
    }


async def handle_confirmation(state: GlobalAgentState) -> dict[str, Any]:
    """Layer 5 — process user's response to the intent summary.

    Three paths:
    1. ``confirmed`` → set ``intent_phase_complete=True``, hand off to connection phase
    2. ``partial_correction`` → apply changes, route back through gather nodes
    3. ``full_rejection`` → reset all intent state, start over

    For partial corrections: only the corrected slots are cleared.
    Unchanged slots are preserved — user doesn't re-confirm them.
    """
    user_text = last_user_text(state.messages or [])
    source_id = source_connector_id(state.source) or ""

    classification = await _classify_confirmation(
        user_reply=user_text,
        current_summary=state.intent_summary or "",
        signal_type=state.signal_type,
        source=source_id,
        source_object=state.source_object,
        destinations=list(state.destinations or []),
    )

    response_type = classification["type"]

    # --- Path 1: Confirmed -------------------------------------------------------
    if response_type == "confirmed":
        dest_labels: list[str] = []
        for d in state.destinations or []:
            dest_labels.append(await deps.connector_schema.destination_label(d))
        src_label = await deps.connector_schema.source_label(source_id)

        all_labels = [src_label] + dest_labels
        conn_list = " and ".join(all_labels)
        return {
            "intent_phase": "complete",
            "intent_phase_complete": True,
            "messages": [
                AIMessage(
                    content=json.dumps(
                        {
                            "type": "intent_complete",
                            "event": "intent_phase_complete",
                            "message": (f"Great! I'll now check your connections for {conn_list}."),
                            "phase": "intent",
                            "source": source_id,
                            "source_label": src_label,
                            "source_object": state.source_object,
                            "destinations": state.destinations,
                            "destination_labels": dest_labels,
                            "signal_type": state.signal_type,
                        }
                    )
                )
            ],
        }

    # --- Path 2: Partial correction ----------------------------------------------
    elif response_type == "partial_correction":
        corrections = classification.get("corrections") or []

        if not corrections:
            # Classifier said correction but extracted nothing — ask what changed
            return {
                "intent_phase": "confirming",
                "messages": [
                    AIMessage(
                        content=json.dumps(
                            {
                                "type": "clarification_needed",
                                "event": "correction_unclear",
                                "message": ("I want to make sure I get this right — what would you like to change?"),
                                "phase": "intent",
                            }
                        )
                    )
                ],
            }

        state_updates = _apply_corrections(corrections, state)

        changed_fields = [c["changed_field"] for c in corrections]
        field_labels: dict[str, str] = {
            "signal_type": "signal type",
            "source": "data source",
            "source_object": "Salesforce object",
            "destinations": "destinations",
        }
        changed_display = ", ".join(str(field_labels.get(f, f)) for f in changed_fields)

        return {
            **state_updates,
            "messages": [
                AIMessage(
                    content=json.dumps(
                        {
                            "type": "intent_correction",
                            "event": "correction_applied",
                            "message": (f"Got it — let me update the {changed_display} and confirm again."),
                            "phase": "intent",
                            "corrected_fields": changed_fields,
                        }
                    )
                )
            ],
        }

    # --- Path 3: Full rejection --------------------------------------------------
    else:
        return {
            **_MAPPING_RESET_KEYS,
            "signal_type": None,
            "signal_type_confidence": None,
            "source": None,
            "source_object": "",
            "destinations": [],
            "intent_phase": "idle",
            "intent_phase_complete": False,
            "intent_summary": None,
            "pending_clarification": None,
            "clarifications_asked": [],
            "messages": [
                AIMessage(
                    content=json.dumps(
                        {
                            "type": "intent_reset",
                            "event": "intent_restarted",
                            "message": ("No problem — let's start fresh. What would you like to set up?"),
                            "phase": "intent",
                        }
                    )
                )
            ],
        }
