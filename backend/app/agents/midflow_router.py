"""Mid-flow NL router — classifies user turns during an active setup flow.

Called when intent_phase_complete=True and the user message
doesn't look like a direct answer to the current interrupt.

Action types:
  add_destination    — "also add TikTok"
  remove_destination — "remove Meta" (destructive — needs confirm token)
  change_object      — "use Contact instead" (destructive)
  edit_mapping       — "change the email mapping"
  edit_funnel        — "change the funnel stages"
  show_mapping       — "show me the current mapping"
  affirm             — "yes", "looks good", "continue"
  deny               — "no", "go back"
  question           — user asking a clarifying question
  out_of_scope       — unrelated to the setup flow
  provide_value      — user providing a specific value or field name
"""

from __future__ import annotations

import json
import re
from typing import Any

_AFFIRM_RE = re.compile(
    r"^\s*(yes|yeah|yep|yup|ok|okay|sure|correct|right|looks?\s*good|"
    r"confirm|continue|proceed|go\s*ahead|sounds?\s*good|perfect|great|"
    r"approved?|accept|done|next|let['']s\s*go)\s*[.!]?\s*$",
    re.I,
)
_DENY_RE = re.compile(
    r"^\s*(no|nope|nah|cancel|stop|abort|back|undo|restart|"
    r"go\s*back|start\s*over|not\s*right|wrong|incorrect)\s*[.!]?\s*$",
    re.I,
)
_SHOW_MAPPING_RE = re.compile(
    r"(show|display|see|view|check|review)\s+(me\s+)?(the\s+)?(current\s+)?"
    r"(mapping|mappings|matrix|fields?)",
    re.I,
)
_ADD_DEST_RE = re.compile(
    r"(add|include|also\s+add|connect|enable)\s+.*(tiktok|snapchat|linkedin|"
    r"twitter|bing|google|meta|facebook)",
    re.I,
)
_REMOVE_DEST_RE = re.compile(
    r"(remove|exclude|disable|drop|skip|don['']t\s+use)\s+.*(tiktok|snapchat|"
    r"linkedin|twitter|bing|google|meta|facebook)",
    re.I,
)

_DEST_SLUG_MAP = {
    "meta": "meta_capi",
    "facebook": "meta_capi",
    "google": "google_offline",
    "google offline": "google_offline",
    "google dm": "google_dm",
    "google customer match": "google_dm",
    "tiktok": "tiktok",
    "snap": "snapchat",
    "snapchat": "snapchat",
    "linkedin": "linkedin",
    "twitter": "twitter",
    "bing": "bing",
}


def _extract_dest_mentions(text: str) -> list[str]:
    text_lower = text.lower()
    found = []
    for keyword, slug in _DEST_SLUG_MAP.items():
        if keyword in text_lower and slug not in found:
            found.append(slug)
    return found


def classify_midflow_action(
    user_text: str,
    state: Any,
) -> dict[str, Any]:
    """Classify a mid-flow user message into an action dict.

    Returns: {action: str, destinations?: list[str], details?: str}
    """
    text = (user_text or "").strip()

    if _AFFIRM_RE.match(text):
        return {"action": "affirm"}

    if _DENY_RE.match(text):
        return {"action": "deny"}

    if _SHOW_MAPPING_RE.search(text):
        return {"action": "show_mapping"}

    if _ADD_DEST_RE.search(text):
        dests = _extract_dest_mentions(text)
        return {"action": "add_destination", "destinations": dests}

    if _REMOVE_DEST_RE.search(text):
        dests = _extract_dest_mentions(text)
        return {"action": "remove_destination", "destinations": dests, "requires_confirm": True}

    return _llm_classify(text, state)


def _llm_classify(text: str, state: Any) -> dict[str, Any]:
    """Use LLM to classify ambiguous mid-flow messages."""
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage
        from pydantic import SecretStr

        from app.config import settings

        llm = ChatOpenAI(
            model=getattr(settings, "DEFAULT_LLM_MODEL", "gpt-4o-mini"),
            temperature=0,
            api_key=SecretStr(settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None,
        )
        current_phase = _phase_label(state)
        prompt = (
            f"You are classifying a user message during a Signals setup flow. "
            f"Current phase: {current_phase}. "
            f"Classify the message into exactly one action:\n"
            f"add_destination, remove_destination, change_object, edit_mapping, "
            f"edit_funnel, show_mapping, affirm, deny, question, out_of_scope, provide_value\n\n"
            f"Message: {text!r}\n\n"
            f'Reply with JSON only: {{"action": "<action>", "details": "<optional detail>"}}'
        )
        result = llm.invoke([HumanMessage(content=prompt)])
        raw_content = result.content
        text = raw_content if isinstance(raw_content, str) else str(raw_content)
        parsed = json.loads(text.strip())
        return {
            "action": parsed.get("action", "question"),
            "details": parsed.get("details", ""),
        }
    except Exception:
        return {"action": "question"}


def _phase_label(state: Any) -> str:
    if not getattr(state, "intent_phase_complete", False):
        return "intent"
    if not getattr(state, "connection_phase_complete", False):
        return "connection"
    if not getattr(state, "source_object_phase_complete", False):
        return "source object"
    if not getattr(state, "funnel_phase_complete", False):
        return "funnel"
    if not getattr(state, "mapping_phase_complete", False):
        return "mapping"
    if not getattr(state, "validation_phase_complete", False):
        return "validation"
    if not getattr(state, "confirmation_phase_complete", False):
        return "confirmation"
    return "activation"


def handle_midflow_action(
    action_result: dict[str, Any],
    state: Any,
) -> dict[str, Any] | None:
    """Convert a classified action into a state update dict.

    Returns a partial state update, or None if the current worker should handle it.
    """
    action = action_result.get("action", "question")
    destinations = action_result.get("destinations", [])

    if action == "add_destination":
        active = list(getattr(state, "active_destinations", []) or [])
        new_dests = [d for d in destinations if d not in active]
        if not new_dests:
            return None
        return {
            "active_destinations": active + new_dests,
            "connection_phase_complete": False,
            "mapping_phase_complete": False,
            "validation_phase_complete": False,
            "confirmation_phase_complete": False,
            "confirmed_config_hash": None,
            "pending_action": f"add_destination:{','.join(new_dests)}",
        }

    if action == "remove_destination":
        return {
            "pending_action": f"remove_destination:{','.join(destinations)}",
        }

    if action == "change_object":
        return {
            "pending_action": "change_object",
            "confirmed_config_hash": None,
        }

    if action == "edit_mapping":
        return {
            "mapping_phase_complete": False,
            "validation_phase_complete": False,
            "confirmation_phase_complete": False,
            "confirmed_config_hash": None,
            "pending_action": "edit_mapping",
        }

    if action == "edit_funnel":
        return {
            "funnel_phase_complete": False,
            "mapping_phase_complete": False,
            "validation_phase_complete": False,
            "confirmed_config_hash": None,
        }

    if action == "show_mapping":
        return {"pending_action": "show_mapping"}

    if action == "out_of_scope":
        return {"pending_action": "out_of_scope"}

    # affirm, deny, question, provide_value — pass through to current worker
    return None
