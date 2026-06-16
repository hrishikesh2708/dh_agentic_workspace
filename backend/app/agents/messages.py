"""Agent message builders — narration events, intent acks, mapping payloads.

Ported from ``crawler_agent/src/graph/messages.py``. Differences:

- All ``src.*`` imports rewritten to ``app.agents.*`` / ``app.schemas.agent.*``.
- ``MappingRouterState`` (TypedDict) replaced with :class:`GlobalAgentState`
  (Pydantic). All ``state.get("foo")`` are now ``state.foo``.
- Where the original returned ``state.get("mappings")`` (already a list of
  dicts), we now call ``[m.model_dump() for m in state.mappings]`` because
  the unified state stores :class:`ProposedMapping` objects.
"""

from __future__ import annotations

import json
import re
from typing import (
    Any,
    Literal,
)

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
)

from app.agents import deps
from app.agents.constants import (
    INTENT_PHASE,
    source_label,
)
from app.agents.intent_validation import (
    canonicalize_object_name,
    is_valid_destination,
    is_valid_source,
    normalize_optional_str,
    source_connector_id,
)
from app.agents.narratives import (
    CANONICAL_LABEL,
    CANONICAL_STEP_INDEX,
    CANONICAL_STEP_TOTAL,
    INTENT_STEP_INDEX,
    INTENT_STEP_TOTAL,
    PROJECTION_STEP_INDEX,
    PROJECTION_STEP_TOTAL,
    get_template,
    render_template,
)
from app.agents.orchestrator.state import GlobalAgentState

IntentGatherStep = Literal["source", "object", "destination"]
IntentStepStatus = Literal["in_progress", "confirmed", "awaiting_input"]

_NARRATOR_SYSTEM = """Summarize the user's mapping goal in one friendly sentence.
Return ONLY JSON: {"message": "<one sentence>"}
Use ONLY the validated fields listed. Do not mention sources, objects, or destinations that are not in the validated list."""

_PARSE_ACK_SYSTEM = """You are confirming what you understood from the user's data mapping request.
Write one short, friendly sentence summarising their goal.
Mention signal type (e.g. "offline conversions"), source, object, and destinations only when they appear in the parsed fields.
Return ONLY JSON: {"message": "<one sentence>"}"""


async def destination_label(dest_id: str) -> str:
    """Resolve a destination ID to its label via the catalog."""
    return await deps.connector_schema.destination_label(dest_id)


def _event_id(phase: str, step: str, status: str) -> str:
    if phase == INTENT_PHASE and step == "requirements":
        return "requirements_gathering"
    return f"{phase}_{step}_{status}"


def _step_meta(phase: str, step: str) -> tuple[int | None, int | None]:
    if phase == INTENT_PHASE:
        idx = INTENT_STEP_INDEX.get(step)
        return (idx, INTENT_STEP_TOTAL if idx is not None else None)
    if phase == "canonical":
        idx = CANONICAL_STEP_INDEX.get(step)
        return (idx, CANONICAL_STEP_TOTAL if idx is not None else None)
    if phase == "projection":
        idx = PROJECTION_STEP_INDEX.get(step)
        return (idx, PROJECTION_STEP_TOTAL if idx is not None else None)
    return (None, None)


def narrative_message(
    phase: str,
    step: str,
    status: str,
    *,
    labels: dict[str, str] | None = None,
    source: str = "",
    source_label_value: str = "",
    source_object: str = "",
    destination_type: str = "",
    destination_label_value: str = "",
    run_mode: str = "",
) -> AIMessage:
    """Build a narration AIMessage (JSON content) for a phase/step/status combo."""
    label_map = {
        "source_label": source_label_value or (source_label(source) if source else ""),
        "dest_label": destination_label_value,
        "object": source_object,
        "canonical_label": CANONICAL_LABEL,
        **(labels or {}),
    }
    template = get_template(phase, step, status)
    message = render_template(template, label_map) if template else f"{phase} · {step}"
    step_index, step_total = _step_meta(phase, step)

    payload: dict[str, Any] = {
        "type": "agent_event",
        "event": _event_id(phase, step, status),
        "message": message,
        "phase": phase,
        "step": step,
        "status": status,
    }
    if step_index is not None:
        payload["step_index"] = step_index
    if step_total is not None:
        payload["step_total"] = step_total
    if source:
        payload["source"] = source
    if label_map.get("source_label"):
        payload["source_label"] = label_map["source_label"]
    if source_object:
        payload["source_object"] = source_object
    if destination_type:
        payload["destination_type"] = destination_type
    if label_map.get("dest_label"):
        payload["destination_label"] = label_map["dest_label"]
    if run_mode:
        payload["run_mode"] = run_mode
    return AIMessage(content=json.dumps(payload))


async def intent_narrator_message(
    user_text: str,
    *,
    source: str,
    source_object: str,
    destination_type: str,
) -> AIMessage | None:
    """Compose the LLM-narrated 'I figured out you want to...' intent ack."""
    validated_parts: list[str] = []
    src_label = ""
    dest_label = ""
    obj = (source_object or "").strip()

    if source:
        valid_source_ids = await deps.connector_schema.enabled_source_ids()
        if is_valid_source(source, valid_source_ids):
            src_label = await deps.connector_schema.source_label(source)
            validated_parts.append(f"source: {src_label}")
    if obj:
        validated_parts.append(f"object: {obj}")
    if destination_type:
        valid_ids = await deps.connector_schema.enabled_destination_ids()
        if is_valid_destination(destination_type, valid_ids):
            dest_label = await destination_label(destination_type)
            validated_parts.append(f"destination: {dest_label}")

    if not validated_parts:
        return None

    message = ""
    if deps.openai.client:
        parsed = await deps.openai.chat_json(
            _NARRATOR_SYSTEM,
            f"User message: {user_text}\nValidated fields: {', '.join(validated_parts)}",
        )
        message = str(parsed.get("message") or "").strip()

    if not message:
        if obj and src_label and dest_label:
            message = f"I figured out you want to map {obj} from {src_label} to {dest_label}."
        elif obj and src_label:
            message = f"I figured out you want to map {obj} from {src_label}."
        elif src_label and dest_label:
            message = f"I figured out you want to connect {src_label} to {dest_label}."
        elif src_label:
            message = f"I figured out you want to use {src_label}."
        else:
            return None

    payload: dict[str, Any] = {
        "type": "intent_ack",
        "event": "intent_understood",
        "message": message,
        "phase": INTENT_PHASE,
    }
    if source:
        payload["source"] = source
        payload["source_label"] = src_label
    if obj:
        payload["source_object"] = obj
    if destination_type:
        payload["destination_type"] = destination_type
        payload["destination_label"] = dest_label
    return AIMessage(content=json.dumps(payload))


async def intent_parse_ack_message(
    user_text: str,
    *,
    signal_type: str | None,
    source_label_str: str,
    source_object: str,
    destination_labels: list[str],
) -> AIMessage | None:
    """LLM-generated contextual ack emitted by parse_initial_intent (Layer 1).

    Replaces ``intent_narrator_message`` for the initial parse step.
    Returns ``None`` when there is nothing useful to ack (no parsed slots at all).
    """
    parts: list[str] = []
    if signal_type:
        parts.append(f"signal type: {signal_type.replace('_', ' ')}")
    if source_label_str:
        parts.append(f"source: {source_label_str}")
    if source_object:
        parts.append(f"object: {source_object}")
    if destination_labels:
        parts.append(f"destinations: {', '.join(destination_labels)}")

    if not parts:
        return None

    message = ""
    if deps.openai.client:
        try:
            context = f"User message: {user_text}\nParsed fields: {'; '.join(parts)}"
            parsed = await deps.openai.chat_json(_PARSE_ACK_SYSTEM, context)
            message = str(parsed.get("message") or "").strip()
        except Exception:
            pass

    if not message:
        # Fallback template — compose from available slots
        if source_label_str and source_object and destination_labels:
            dest_str = " and ".join(destination_labels)
            message = f"Got it — I'll map {source_object} from {source_label_str} to {dest_str}."
        elif source_label_str and destination_labels:
            dest_str = " and ".join(destination_labels)
            message = f"Got it — I'll connect {source_label_str} to {dest_str}."
        elif source_label_str and source_object:
            message = f"Got it — mapping {source_object} from {source_label_str}."
        elif destination_labels:
            dest_str = " and ".join(destination_labels)
            message = f"Got it — I'll set up a mapping to {dest_str}."
        elif source_label_str:
            message = f"Got it — using {source_label_str} as the source."
        else:
            return None

    payload: dict[str, Any] = {
        "type": "intent_ack",
        "event": "parse_ack",
        "message": message,
        "phase": INTENT_PHASE,
    }
    if signal_type:
        payload["signal_type"] = signal_type
    if source_label_str:
        payload["source_label"] = source_label_str
    if source_object:
        payload["source_object"] = source_object
    if destination_labels:
        payload["destination_labels"] = destination_labels
    return AIMessage(content=json.dumps(payload))


async def intent_gather_event(
    step: IntentGatherStep,
    status: IntentStepStatus,
    *,
    source_id: str = "",
    source_object: str = "",
    destination_id: str = "",
) -> AIMessage:
    """Narration for an intent_worker gather step (source / object / destination)."""
    dest_label = await destination_label(destination_id) if destination_id else ""
    src_label = await deps.connector_schema.source_label(source_id) if source_id else ""
    return narrative_message(
        INTENT_PHASE,
        step,
        status,
        source=source_id,
        source_label_value=src_label,
        source_object=source_object,
        destination_type=destination_id,
        destination_label_value=dest_label,
    )


async def intent_complete_message(
    *,
    source: str,
    source_object: str,
    destination_type: str,
    run_mode: str,
    available_objects: list[str] | None = None,
    valid_destination_ids: set[str] | None = None,
) -> AIMessage | None:
    """'Setup complete' ack at the end of the intent phase."""
    valid_source_ids = await deps.connector_schema.enabled_source_ids()
    if not is_valid_source(source, valid_source_ids):
        return None

    obj = (source_object or "").strip()
    if available_objects:
        canonical = canonicalize_object_name(obj, available_objects)
        if not canonical:
            return None
        obj = canonical
    elif not obj:
        return None

    dest = (destination_type or "").strip().lower()
    if valid_destination_ids is not None:
        if not is_valid_destination(dest, valid_destination_ids):
            return None
    elif not dest:
        return None

    src_label = await deps.connector_schema.source_label(source)
    dest_label = await destination_label(dest)
    labels = {
        "source_label": src_label,
        "dest_label": dest_label,
        "object": obj,
    }
    message = render_template(get_template(INTENT_PHASE, "complete", "message"), labels)
    subtitle = get_template(INTENT_PHASE, "complete", "subtitle") or "Setup complete"

    payload: dict[str, Any] = {
        "type": "intent_ack",
        "complete": True,
        "subtitle": subtitle,
        "message": message or f"Ready to map {obj} from {src_label} to {dest_label}.",
        "source": source,
        "source_label": src_label,
        "source_object": obj,
        "destination_type": dest,
        "destination_label": dest_label,
        "run_mode": run_mode,
        "phase": INTENT_PHASE,
    }
    return AIMessage(content=json.dumps(payload))


async def canonical_narrative_event(
    step: str,
    status: str,
    state: GlobalAgentState,
    *,
    labels: dict[str, str] | None = None,
) -> AIMessage:
    """Narration for a canonical-phase step (bridge / map)."""
    source = normalize_optional_str(source_connector_id(state.source)) or "salesforce"
    src_label = await deps.connector_schema.source_label(source)
    obj = state.source_object or "records"
    dest_type = state.destination_type or ""
    dest_label = await destination_label(dest_type) if dest_type else ""
    base = {
        "source_label": src_label,
        "object": obj,
        "dest_label": dest_label,
        "canonical_label": CANONICAL_LABEL,
        **(labels or {}),
    }
    return narrative_message(
        "canonical",
        step,
        status,
        labels=base,
        source=source,
        source_label_value=base["source_label"],
        source_object=obj,
        destination_type=dest_type,
        destination_label_value=dest_label,
    )


async def projection_narrative_event(
    step: str,
    status: str,
    state: GlobalAgentState,
) -> AIMessage:
    """Narration for a projection-phase step (setup / map)."""
    dest_type = state.destination_type or ""
    dest_label = await destination_label(dest_type)
    return narrative_message(
        "projection",
        step,
        status,
        labels={"dest_label": dest_label},
        destination_type=dest_type,
        destination_label_value=dest_label,
    )


def destination_field_options(state: GlobalAgentState) -> list[dict]:
    """Flatten the destination schema for a UI picker."""
    dest = state.destination_schema
    if not dest:
        return []
    return [
        {
            "name": f.name,
            "label": f.name,
            "type": f.type,
            "required": f.required,
            "description": f.description or "",
        }
        for f in dest.fields
    ]


def build_mapping_complete_payload(
    mappings: list[dict],
    *,
    mapping_kind: str,
    summary: str,
    source_object: str,
    source_label: str,
    destination_label: str,
    destination_type: str,
    session_id: int | None = None,
) -> dict[str, Any]:
    """Final 'mapping_complete' payload sent to the UI after a stage finishes."""
    auto = sum(1 for m in mappings if m.get("status") == "auto_approved")
    human = sum(1 for m in mappings if m.get("status") in {"human_approved", "human_corrected"})
    return {
        "type": "mapping_complete",
        "summary": summary,
        "source_label": source_label,
        "source_object": source_object,
        "destination_label": destination_label,
        "destination_type": destination_type,
        "mapping_kind": mapping_kind,
        "mappings": mappings,
        "stats": {
            "total": len(mappings),
            "auto_approved": auto,
            "human_reviewed": human,
        },
        "session_id": session_id,
    }


def canonical_stage_complete_message(
    state: GlobalAgentState,
    mappings: list[dict],
    session_id: int | None = None,
) -> AIMessage:
    """'Mapping complete' for the canonical stage (always followed by projection or END)."""
    source_object = state.source_object or "records"
    src_label = state.source.display_name if state.source else source_label(source_connector_id(state.source))
    payload = build_mapping_complete_payload(
        mappings,
        mapping_kind="canonical",
        summary=f"Your {source_object} → Datahash canonical mappings are confirmed.",
        source_object=source_object,
        source_label=src_label,
        destination_label="Datahash Canonical",
        destination_type="canonical",
        session_id=session_id if session_id is not None else state.session_id,
    )
    return AIMessage(content=json.dumps(payload))


async def mapping_complete_message(state: GlobalAgentState) -> AIMessage:
    """Final 'mapping_complete' message (sent by done_summary)."""
    mappings = [m.model_dump() for m in state.mappings]
    run_mode = state.run_mode or "canonical_only"
    mapping_kind = "projection" if run_mode == "projection" else "canonical"
    source_object = state.source_object or "records"
    src_label = await deps.connector_schema.source_label(source_connector_id(state.source))
    dest_label = await destination_label(state.destination_type or "")

    if mapping_kind == "projection":
        summary = f"Your {source_object} → {dest_label} mappings are ready."
    else:
        summary = f"Your {source_object} → Datahash canonical mappings are ready."

    payload = build_mapping_complete_payload(
        mappings,
        mapping_kind=mapping_kind,
        summary=summary,
        source_object=source_object,
        source_label=src_label,
        destination_label=dest_label,
        destination_type=state.destination_type or "",
        session_id=state.session_id,
    )
    return AIMessage(content=json.dumps(payload))


def last_user_text(messages: list[BaseMessage]) -> str:
    """Extract the most recent user message text from a list of LangChain messages."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = msg.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
                ).strip()
    return ""


def extract_json(text: str) -> dict:
    """Best-effort JSON parser tolerant of code-fenced or noisy LLM output."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return {}
