"""welcome_worker node — personalised greeting on chat connect."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.graph import END

from app.agents.core.messages import last_user_text
from app.agents.orchestrator.state import GlobalAgentState
from app.core.logging import logger
from app.services.database import database_service

_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "core" / "prompts" / "welcome_message.txt"
_DEFAULT_TEMPLATE = "Hi {display_name}, what signals would you want to send, and where? Describe it in your own words."


def _load_welcome_template() -> str:
    if not _PROMPT_PATH.exists():
        return _DEFAULT_TEMPLATE
    text = _PROMPT_PATH.read_text(encoding="utf-8").strip()
    return text or _DEFAULT_TEMPLATE


def _display_name_from_email(email: str) -> str:
    local = email.split("@", 1)[0].strip()
    return local or "there"


async def _resolve_display_name(state: GlobalAgentState) -> str:
    """Resolve a friendly name from state, then the user table."""
    if state.username and state.username.strip():
        return state.username.strip()

    customer_id = state.customer_id
    if customer_id is None:
        return "there"

    try:
        user = await database_service.get_user(customer_id)
    except Exception:
        logger.exception("welcome_user_lookup_failed", customer_id=customer_id)
        return "there"

    if user is None:
        return "there"
    if user.username and user.username.strip():
        return user.username.strip()
    if user.email:
        return _display_name_from_email(user.email)
    return "there"


def render_welcome_message(display_name: str) -> str:
    """Format the welcome prompt template with the user's display name."""
    template = _load_welcome_template()
    try:
        return template.format(display_name=display_name)
    except KeyError:
        return _DEFAULT_TEMPLATE.format(display_name=display_name)


async def welcome_user(state: GlobalAgentState) -> dict[str, Any]:
    """Emit a welcome message on connect (no user message in the turn yet)."""
    if last_user_text(state.messages or []):
        return {}

    display_name = await _resolve_display_name(state)
    message = render_welcome_message(display_name)

    update: dict[str, Any] = {
        "messages": [AIMessage(content=message)],
    }
    if state.customer_id is not None:
        update["customer_id"] = state.customer_id
    if not state.username and display_name != "there":
        update["username"] = display_name
    return update


def route_after_welcome(state: GlobalAgentState) -> str:
    """Continue to intent when the user has sent a message; otherwise pause."""
    if last_user_text(state.messages or []):
        return "intent"
    return END
