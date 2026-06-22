"""welcome_worker node — personalised greeting on chat connect."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END

from app.agents import deps
from app.agents.messages import last_user_text
from app.agents.orchestrator.state import GlobalAgentState
from app.core.logging import logger
from app.services.database import database_service

# All agent prompts live here
_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "welcome_message.txt"

# Bare greeting guard — ported from ai-agent-poc adapters.py.
# The LLM classifies "hi" / "hello" as out-of-scope, so without this guard a
# bare greeting on first connect would land in intent_worker and confuse the parser.
# Anchored tightly to pure greetings so it never swallows a real request.
_GREETING_RE = re.compile(
    r"^\s*("
    r"(hi|hello|hey|hiya|yo|howdy|greetings)(\s+(there|team|all|everyone))?"
    r"|good\s+(morning|afternoon|evening)"
    r")[\s!.,?]*$",
    re.IGNORECASE,
)

# Capabilities / help question guard — "what can you do?", "what do you support?", etc.
# These should return a capabilities answer directly rather than going through intent parsing.
_CAPABILITIES_RE = re.compile(
    r"\b("
    r"what\s+(can\s+you|do\s+you)\s+(do|support|help|set\s+up)"
    r"|what\s+(is\s+)?(supported|available)"
    r"|what\s+sources?"
    r"|what\s+destinations?"
    r"|how\s+does\s+this\s+work"
    r"|tell\s+me\s+(more|about\s+(this|what\s+you))"
    r")\b",
    re.IGNORECASE,
)


def _welcome_already_sent(messages: list[BaseMessage]) -> bool:
    """True if an AI message already exists — welcome was already shown."""
    return any(isinstance(m, AIMessage) for m in messages)


def _is_bare_greeting(text: str) -> bool:
    return bool(_GREETING_RE.match(text.strip()))


def _is_capabilities_question(text: str) -> bool:
    return bool(_CAPABILITIES_RE.search(text.strip()))


async def _resolve_display_name(state: GlobalAgentState) -> str:
    """Username from state (injected from session) → DB fallback → 'there'."""
    if state.username and state.username.strip():
        return state.username.strip()

    try:
        user = await database_service.get_user(state.user_id)
        if user and user.username and user.username.strip():
            return user.username.strip()
    except Exception:
        logger.exception("welcome_username_lookup_failed", user_id=state.user_id)

    return "there"


async def _generate_welcome_message(display_name: str) -> str | None:
    """Ask OpenAI to generate a greeting."""
    if not _PROMPT_PATH.exists():
        logger.warning("welcome_prompt_missing", path=str(_PROMPT_PATH))
        return None

    if not deps.openai.client:
        logger.warning("welcome_openai_client_unavailable")
        return None

    prompt = _PROMPT_PATH.read_text(encoding="utf-8").strip()
    if not prompt:
        logger.warning("welcome_prompt_empty", path=str(_PROMPT_PATH))
        return None

    try:
        parsed = await deps.openai.chat_json(prompt, f"Display name: {display_name}")
        message = str(parsed.get("message") or "").strip()
        if message:
            return message
    except Exception:
        logger.exception("welcome_message_generation_failed", display_name=display_name)

    return None


async def welcome_user(state: GlobalAgentState) -> dict[str, Any]:
    """Emit a welcome message on first connect, then run mid-flow routing on subsequent turns.

    On the first connect (no AI messages yet): generates and emits the welcome message.
    On subsequent turns when intent_phase_complete=True: classifies the user message
    for mid-flow corrections (add/remove destination, edit mapping, etc.) and returns
    a state update if the action is recognised. The supervisor will re-route based on
    the updated state.
    """
    # Mid-flow NL routing — classify corrections during active setup
    if state.intent_phase_complete:
        try:
            from app.agents.midflow_router import classify_midflow_action, handle_midflow_action

            # Get the latest user message
            from langchain_core.messages import HumanMessage

            user_text = ""
            for msg in reversed(state.messages):
                if isinstance(msg, HumanMessage) or (hasattr(msg, "role") and getattr(msg, "role", "") == "user"):
                    user_text = str(msg.content)
                    break

            if user_text:
                action_result = classify_midflow_action(user_text, state)
                midflow_update = handle_midflow_action(action_result, state)
                if midflow_update is not None:
                    # Return the state update — supervisor will re-route
                    return midflow_update
        except Exception:
            pass  # Mid-flow routing is best-effort — don't break the main flow

    if _welcome_already_sent(state.messages or []):
        return {}

    display_name = await _resolve_display_name(state)
    message = await _generate_welcome_message(display_name)
    if not message:
        return {}

    update: dict[str, Any] = {"messages": [AIMessage(content=message)]}
    if not state.username and display_name != "there":
        update["username"] = display_name
    return update


def route_after_welcome(state: GlobalAgentState) -> str:
    """After welcome: route based on conversation state across all 8 phases.

    Priority order (top = highest):
    1. No user message yet → END (wait for first message).
    2. Bare greeting ("hi", "hello") before intent starts → END (welcome shown, wait).
    3. Capabilities question before intent starts → END (let welcome handle it).
    4. Intent clarification/confirmation in progress → resume that loop.
    5. Pipeline already activated → END.
    6. Each phase checked in sequence; if complete, skip to next.
    7. If current phase is incomplete, route to its entry node.

    The string keys returned must match the route map in
    graph.py add_conditional_edges for the "welcome" node.
    """
    user_text = last_user_text(state.messages or [])

    if not user_text:
        return END

    # Greeting / capabilities guard — only applies before intent is underway.
    # Once intent_phase_complete is True the user is mid-flow and any message
    # (even "hi") should be handled by the active phase.
    if not state.intent_phase_complete:
        if _is_bare_greeting(user_text):
            # Welcome already shown; just wait for the user to state their goal.
            return END
        if _is_capabilities_question(user_text):
            # Welcome message already describes capabilities. Return END so the
            # user reads it and follows up with a real goal.
            # TODO: add is_help classification to intent_worker to return a
            # richer capabilities answer (ported from ai-agent-poc nodes.py).
            return END

    # --- Intent phase sub-routing -------------------------------------------
    if state.intent_phase == "clarifying":
        return "handle_clarification"

    if state.intent_phase == "confirming":
        return "handle_confirmation"

    # --- Terminal state -------------------------------------------------------
    if state.pipeline_activated:
        return END

    # --- Phase-by-phase routing ----------------------------------------------
    if not state.intent_phase_complete:
        return "intent"

    if not state.connection_phase_complete:
        # Connection phase is autonomous (no user input needed after intent).
        # Returning END here lets the supervisor wait — connection_worker will
        # be triggered in the same turn by the connection phase wiring.
        return END

    if not state.funnel_phase_complete:
        return "funnel_phase"

    if not state.mapping_phase_complete:
        return "mapping_phase"

    if not state.validation_phase_complete:
        if state.pending_action == "edit_mapping":
            return "mapping_phase"
        return "validation_phase"

    if not state.confirmation_phase_complete:
        return "confirm_phase"

    # All phases complete but not yet activated (e.g. user resumed a session)
    return "activation_phase"
