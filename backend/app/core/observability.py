"""Observability module for the application."""

import os

from langsmith import Client

from app.core.config import settings
from app.core.logging import logger


def langsmith_init() -> None:
    """Configure LangSmith tracing via environment variables.

    When LANGSMITH_TRACING is true, LangChain auto-attaches LangChainTracer
    to all runnable invocations — no explicit callback handler is required.
    """
    os.environ["LANGSMITH_TRACING"] = "true" if settings.LANGSMITH_TRACING_ENABLED else "false"

    if settings.LANGSMITH_API_KEY:
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY

    if settings.LANGSMITH_PROJECT:
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT

    if settings.LANGSMITH_ENDPOINT:
        os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT

    if not settings.LANGSMITH_TRACING_ENABLED:
        logger.debug("langsmith_tracing_disabled")
        return

    if not settings.LANGSMITH_API_KEY:
        logger.debug("langsmith_api_key_missing")
        return

    try:
        client = Client(
            api_key=settings.LANGSMITH_API_KEY,
            api_url=settings.LANGSMITH_ENDPOINT,
        )
        client.list_projects(limit=1)
        logger.debug("langsmith_auth_success")
    except Exception as e:
        logger.debug("langsmith_auth_failure", error=str(e))
