"""intent_worker node functions + interrupt-payload builders.

Ported from two crawler_agent files:

- ``src/graph/nodes/intent.py``  → ``parse_initial_intent``,
   ``gather_source``, ``gather_object``, ``gather_destination`` (+ private
   helpers ``_build_parse_system_prompt``, ``_resume_selected``,
   ``_finish_phase_one``).
- ``src/graph/interrupts.py``    → ``build_select_source_interrupt``,
   ``build_select_object_interrupt``, ``build_select_destination_interrupt``,
   ``build_unsupported_source_interrupt`` (the intent-picker HITL payloads;
   the mapping_review payload moved to ``reviewer_worker.tools``).

Differences from crawler_agent:

- All ``state.get("foo")`` → ``state.foo`` (the state is now
  :class:`GlobalAgentState`, a Pydantic model, not a TypedDict).
- ``MAPPING_RESET_KEYS["source"]`` was originally ``""``; we now
  return :class:`Sources.salesforce` since the unified state's ``source``
  field is typed as :class:`Sources` (not ``str``). On reset we still need
  a valid enum; ``salesforce`` is the default. The original
  ``str``-based comparison code (``is_valid_source(source)``) stays
  intact because we coerce to lowercase strings inside the helpers.
- The original returned an empty string ``""`` for ``run_mode`` when
  destination was missing; we keep that — ``run_mode`` is plain ``str``.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from app.agents.core import deps
from app.agents.core.constants import (
    INTENT_PHASE,
    INTENT_PICKERS,
    SOURCE_OPTIONS,
    source_label,
)
from app.agents.core.intent_validation import (
    canonicalize_object_name,
    compute_run_mode,
    enabled_source_options,
    first_enabled_source_id,
    is_valid_destination,
    is_valid_source,
    normalize_optional_str,
)
from app.agents.core.messages import (
    intent_complete_message,
    intent_gather_event,
    intent_narrator_message,
    last_user_text,
    narrative_message,
)
from app.agents.orchestrator.state import GlobalAgentState
from app.schemas.agent.types import Sources

_SUPPORTED_OBJECT_SOURCES = frozenset({"salesforce"})

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


def build_select_source_interrupt() -> dict:
    """HITL payload for picking a source CRM."""
    picker = INTENT_PICKERS["source"]
    enabled = enabled_source_options()
    default = enabled[0]["id"] if enabled else None
    return {
        "type": "select_source",
        "phase": INTENT_PHASE,
        "title": picker["title"],
        "message": picker["message"],
        "hint": None,
        "options": SOURCE_OPTIONS,
        "requested": None,
        "default_selected": default,
    }


def build_select_object_interrupt(
    *,
    source: str,
    objects: list[str],
    requested: str | None,
) -> dict:
    """HITL payload for picking a source object (Lead/Contact/etc.)."""
    src_label = source_label(source)
    matched = canonicalize_object_name(requested, objects)
    default = matched or (objects[0] if objects else None)
    hint = None
    if requested and not matched:
        hint = f'"{requested}" was not found — pick from available objects below.'
    return {
        "type": "select_object",
        "phase": INTENT_PHASE,
        "title": f"Select object for {src_label}",
        "message": f"Which {src_label} object do you want to map?",
        "hint": hint,
        "options": objects,
        "requested": requested,
        "default_selected": default,
    }


def build_select_destination_interrupt(
    *,
    options: list[dict],
    requested: str | None = None,
) -> dict:
    """HITL payload for picking a destination type (canonical/meta_capi/...)."""
    picker = INTENT_PICKERS["destination"]
    valid = [o for o in options if o.get("enabled", True)]
    default = valid[0]["id"] if valid else None
    if requested:
        match = next(
            (o["id"] for o in valid if o["id"].lower() == requested.lower()),
            None,
        )
        if match:
            default = match
    return {
        "type": "select_destination",
        "phase": INTENT_PHASE,
        "title": picker["title"],
        "message": picker["message"],
        "hint": None,
        "options": options,
        "requested": requested,
        "default_selected": default,
    }


def build_unsupported_source_interrupt(*, source: str) -> dict:
    """HITL payload telling the user to re-pick a source (theirs isn't supported yet)."""
    picker = INTENT_PICKERS["source"]
    option = next((o for o in SOURCE_OPTIONS if o["id"] == source.lower()), None)
    label = str(option["label"]) if option else source
    enabled = enabled_source_options()
    return {
        "type": "select_source",
        "phase": INTENT_PHASE,
        "title": picker["title"],
        "message": picker["message"],
        "hint": f"{label} is not supported yet. Select an available source.",
        "options": SOURCE_OPTIONS,
        "requested": source,
        "default_selected": enabled[0]["id"] if enabled else None,
    }


# -----------------------------------------------------------------------------
# Private helpers (ported from src/graph/nodes/intent.py)
# -----------------------------------------------------------------------------


async def _build_parse_system_prompt() -> str:
    source_ids = [o["id"] for o in enabled_source_options()]
    dest_ids = sorted(await deps.catalog.enabled_destination_ids())
    source_union = " | ".join(f'"{s}"' for s in source_ids) or '"salesforce"'
    dest_union = " | ".join(f'"{d}"' for d in dest_ids) or '"canonical"'
    return f"""Extract mapping intent from the user message. Return ONLY valid JSON:
{{
  "source": {source_union} | null,
  "source_object": "<source object name e.g. Lead, Contact, Account>" | null,
  "destination": {dest_union} | null
}}
Set a field to null if it is not mentioned or cannot be confidently inferred.
Only use source and destination values from the lists above."""


def _resume_selected(response: Any, *, fallback: str) -> str:
    if not isinstance(response, dict):
        return fallback
    if response.get("approved") is False:
        return fallback
    selected = normalize_optional_str(response.get("selected"))
    return selected or fallback


def _coerce_source(value: str) -> Sources:
    """Coerce a validated lowercase id back to the :class:`Sources` enum."""
    try:
        return Sources(value)
    except ValueError:
        return Sources.salesforce


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
# Node functions (ported from src/graph/nodes/intent.py)
# -----------------------------------------------------------------------------


async def parse_initial_intent(state: GlobalAgentState) -> dict[str, Any]:
    """Parse the latest user message via LLM and reset stale mapping state."""
    user_text = last_user_text(state.messages or [])
    messages: list[Any] = []

    system_prompt = await _build_parse_system_prompt()
    parsed = await deps.openai.chat_json(system_prompt, user_text or "")

    raw_source = normalize_optional_str(parsed.get("source"))
    raw_object = normalize_optional_str(parsed.get("source_object"))
    raw_dest = normalize_optional_str(parsed.get("destination"))

    valid_dest_ids = await deps.catalog.enabled_destination_ids()
    source: str = raw_source if (raw_source and is_valid_source(raw_source)) else ""
    source_object = raw_object or ""
    destination_type: str = raw_dest if (raw_dest and is_valid_destination(raw_dest, valid_dest_ids)) else ""

    narrator = await intent_narrator_message(
        user_text,
        source=source,
        source_object=source_object,
        destination_type=destination_type,
    )
    if narrator:
        messages.append(narrator)
    else:
        messages.append(
            narrative_message(INTENT_PHASE, "requirements", "in_progress"),
        )

    update: dict[str, Any] = {
        **_MAPPING_RESET_KEYS,
        "source_object": source_object,
        "destination_type": destination_type,
        "run_mode": compute_run_mode(destination_type) if destination_type else "",
        "messages": messages,
    }
    # Only set ``source`` when we have a valid value — otherwise leave the
    # field untouched (the state's default is :class:`Sources.salesforce`).
    if source:
        update["source"] = _coerce_source(source)
    return update


async def gather_source(state: GlobalAgentState) -> dict[str, Any]:
    """HITL gather for the source CRM (no-op if already valid)."""
    current = state.source.value if state.source else ""
    source = normalize_optional_str(current) or ""

    if is_valid_source(source):
        return {}

    response: Any = interrupt(build_select_source_interrupt())
    fallback = first_enabled_source_id()
    selected = _resume_selected(response, fallback=fallback)
    if not is_valid_source(selected):
        selected = fallback

    return {
        "source": _coerce_source(selected),
        "messages": [
            await intent_gather_event("source", "confirmed", source_id=selected),
        ],
    }


async def gather_object(state: GlobalAgentState) -> dict[str, Any]:
    """HITL gather for the source object — list eligible objects and pick one."""
    messages: list[Any] = []
    current_source = state.source.value if state.source else ""
    initial_source = normalize_optional_str(current_source) or first_enabled_source_id()
    source = initial_source
    requested = normalize_optional_str(state.source_object)

    if source.lower() not in _SUPPORTED_OBJECT_SOURCES:
        response: Any = interrupt(build_unsupported_source_interrupt(source=source))
        selected_source = _resume_selected(response, fallback=first_enabled_source_id())
        if not is_valid_source(selected_source):
            selected_source = first_enabled_source_id()
        source = selected_source
        requested = None
        if source != initial_source:
            messages.append(await intent_gather_event("source", "confirmed", source_id=source))

    objects: list[str] = list(state.available_objects or [])
    if not objects:
        try:
            objects = await deps.salesforce.list_eligible_objects(
                include_standard=True,
                include_custom=True,
            )
        except Exception:
            objects = [
                "Lead",
                "Contact",
                "Account",
                "Opportunity",
                "Campaign",
                "CampaignMember",
            ]

    canonical_name = canonicalize_object_name(requested, objects)
    if canonical_name:
        result: dict[str, Any] = {
            "source_object": canonical_name,
            "available_objects": objects,
        }
        if source != initial_source:
            result["source"] = _coerce_source(source)
        if messages:
            result["messages"] = messages
        return result

    response = interrupt(
        build_select_object_interrupt(
            source=source,
            objects=objects,
            requested=requested,
        ),
    )
    fallback = objects[0] if objects else "Lead"
    selected = _resume_selected(response, fallback=fallback)
    if selected not in objects:
        selected = canonicalize_object_name(selected, objects) or fallback

    messages.append(
        await intent_gather_event(
            "object",
            "confirmed",
            source_id=source,
            source_object=selected,
        ),
    )
    result = {
        "source_object": selected,
        "available_objects": objects,
        "messages": messages,
    }
    if source != initial_source:
        result["source"] = _coerce_source(source)
    return result


async def gather_destination(state: GlobalAgentState) -> dict[str, Any]:
    """HITL gather for the destination type — closes the intent phase."""
    dest = normalize_optional_str(state.destination_type) or ""
    destination_options = await deps.catalog.list_destination_options()
    valid_ids = await deps.catalog.enabled_destination_ids()

    current_source = state.source.value if state.source else ""
    source = normalize_optional_str(current_source) or first_enabled_source_id()
    source_object = normalize_optional_str(state.source_object) or ""
    objects = list(state.available_objects or [])

    if is_valid_destination(dest, valid_ids):
        dest_lower = dest.lower()
        run_mode = compute_run_mode(dest_lower)
        finish = await _finish_phase_one(
            source=source,
            source_object=source_object,
            destination_type=dest_lower,
            run_mode=run_mode,
            available_objects=objects,
            valid_dest_ids=valid_ids,
            prior_messages=[],
        )
        return {
            "destination_type": dest_lower,
            "run_mode": run_mode,
            "messages": finish,
        }

    response: Any = interrupt(
        build_select_destination_interrupt(
            options=destination_options,
            requested=dest or None,
        ),
    )
    fallback = destination_options[0]["id"] if destination_options else "canonical"
    selected = _resume_selected(response, fallback=fallback)
    if not is_valid_destination(selected, valid_ids):
        selected = next(
            (o["id"] for o in destination_options if o["id"].lower() in valid_ids),
            fallback,
        )

    dest_lower = selected.lower()
    run_mode = compute_run_mode(dest_lower)
    finish = await _finish_phase_one(
        source=source,
        source_object=source_object,
        destination_type=dest_lower,
        run_mode=run_mode,
        available_objects=objects,
        valid_dest_ids=valid_ids,
        prior_messages=[],
    )
    return {
        "destination_type": dest_lower,
        "run_mode": run_mode,
        "messages": finish,
    }
