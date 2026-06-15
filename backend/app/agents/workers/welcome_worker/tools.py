"""welcome_worker node — personalised greeting on chat connect."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END

from app.agents.core import deps
from app.agents.core.messages import last_user_text
from app.agents.orchestrator.state import GlobalAgentState
from app.core.logging import logger
from app.services.database import database_service

# All agent prompts live here
_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "core" / "prompts" / "welcome_message.txt"


def _welcome_already_sent(messages: list[BaseMessage]) -> bool:
    """True if an AI message already exists — welcome was already shown."""
    return any(isinstance(m, AIMessage) for m in messages)


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
    """Emit a welcome message on first connect.

    Skips only if an AI message already exists (welcome was already shown in
    a previous turn). Always fires on the very first connection — even if the
    user sends a message at the same time.
    """
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
    """After welcome: route based on conversation state.

    - No user message yet → END (wait for first message).
    - intent_phase == "clarifying" → route directly to handle_clarification so
      it sees the user's reply to the clarification question (not the original
      message that triggered the question).
    - intent_phase == "confirming" → route directly to handle_confirmation so
      it sees the user's yes/no reply to the intent summary.
    - Anything else → parse_initial_intent (registered as "intent").
    """
    if not last_user_text(state.messages or []):
        return END

    if state.intent_phase == "clarifying":
        return "handle_clarification"

    if state.intent_phase == "confirming":
        return "handle_confirmation"

    # Intent done but connection not complete — wait for connection phase to finish
    if state.intent_phase_complete and not state.connection_phase_complete:
        return END

    # Connection done but mapping not complete — mapping phase runs without user input
    if state.connection_phase_complete and not state.mapping_phase_complete:
        return END

    # Pipeline activated / mapping complete — nothing left to do
    if state.mapping_phase_complete or state.pipeline_activated:
        return END

    return "intent"
