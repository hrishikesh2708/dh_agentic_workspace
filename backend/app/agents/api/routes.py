"""CopilotKit / AG-UI mount point for the mapping agent.

Exposes the supervisor graph as an AG-UI endpoint at
``/api/v1/copilotkit/*``. JWT-authenticated via the framework's
``get_current_session`` dependency.

The :class:`copilotkit.CopilotKitRemoteEndpoint` (the "SDK") is initialised
once in :func:`app.main.lifespan` and stored on ``app.state.copilotkit_sdk``
so every request reuses the same compiled graph + Postgres checkpointer.

Per-request user identity is stashed on ``request.state`` so the graph's
node functions can read ``request.state.customer_id`` if they need to
correlate with the framework's ``user`` table.
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from app.api.v1.auth import get_current_session
from app.core.logging import logger
from app.models.session import Session

router = APIRouter()


async def _get_sdk(request: Request):
    """FastAPI dependency that returns the singleton CopilotKit SDK.

    The SDK is constructed in :func:`app.main.lifespan`. If construction
    failed (e.g. Postgres unavailable in degraded mode) we surface a 503
    so the client gets a clear error.
    """
    sdk = getattr(request.app.state, "copilotkit_sdk", None)
    if sdk is None:
        raise HTTPException(status_code=503, detail="agent not initialized")
    return sdk


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)
async def copilotkit_endpoint(
    request: Request,
    path: str,  # noqa: ARG001 — captured by the catch-all but consumed by the SDK from request.url
    session: Session = Depends(get_current_session),
    sdk=Depends(_get_sdk),
):
    """JWT-gated proxy into the CopilotKit FastAPI handler.

    The CopilotKit SDK reads the HTTP method + body itself; we only do
    auth + per-request bookkeeping before forwarding.
    """
    # Lazy import — avoid pulling the heavy copilotkit module on every cold start.
    from copilotkit.integrations.fastapi import handler as copilotkit_handler

    # Stash session bookkeeping on request.state so any downstream code
    # that wants ``customer_id`` (e.g. learning_worker.persist_session)
    # can pull it from the runnable config in a future iteration.
    request.state.customer_id = session.user_id
    request.state.session_id = session.id

    logger.info(
        "copilotkit_request",
        path=path,
        method=request.method,
        user_id=session.user_id,
        session_id=session.id,
    )
    return await copilotkit_handler(request, sdk)
