"""CopilotKit / AG-UI mount point for the mapping agent.

Exposes the supervisor graph as an AG-UI endpoint at
``/api/v1/copilotkit/*``. JWT-authenticated via the framework's
``get_current_session`` dependency.

The :class:`copilotkit.CopilotKitRemoteEndpoint` (the "SDK") is initialised
once in :func:`app.main.lifespan` and stored on ``app.state.copilotkit_sdk``
so every request reuses the same compiled graph + Postgres checkpointer.

The compiled :class:`copilotkit.LangGraphAGUIAgent` is also stored on
``app.state.langgraph_agent`` because it streams via the AG-UI ``run()``
protocol. The stock CopilotKit FastAPI handler only supports legacy
``execute()`` agents and treats every POST to ``/`` as an info request,
which is why chat messages were getting info JSON back instead of SSE events.

Per-request user identity is stashed on ``request.state`` so the graph's
node functions can read ``request.state.customer_id`` if they need to
correlate with the framework's ``user`` table.
"""

from __future__ import annotations

import re
from typing import Any

from ag_ui.core.types import RunAgentInput
from ag_ui.encoder import EventEncoder
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.v1.auth import get_current_session
from app.core.logging import logger
from app.models.session import Session

router = APIRouter()

_AGENT_PATH_RE = re.compile(r"^agent/(?P<name>[a-zA-Z0-9_-]+)(?:/run)?$")


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


def _get_langgraph_agent(request: Request):
    agent = getattr(request.app.state, "langgraph_agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="agent not initialized")
    return agent


def _is_info_request(body: dict[str, Any] | None, *, path: str, method: str) -> bool:
    if method == "GET" and path in ("", "info"):
        return True
    if body is None:
        return method in ("GET", "POST") and path in ("", "info")
    if body.get("method") == "info":
        return True
    if path == "info" and method == "POST":
        return True
    if body.get("method") in ("agent/run", "agent/connect", "agent/stop"):
        return False
    # Raw AG-UI RunAgentInput (HttpAgent) — not an info probe.
    if body.get("threadId") is not None and body.get("messages") is not None:
        return False
    if _AGENT_PATH_RE.match(path):
        return False
    return method in ("GET", "POST") and path in ("", "info")


def _extract_run_payload(body: dict[str, Any], *, path: str) -> dict[str, Any]:
    method = body.get("method")
    if method in ("agent/run", "agent/connect"):
        params = body.get("params") or {}
        requested = params.get("agentId") or params.get("agent_id")
        if requested and requested != "datahash_agent":
            raise HTTPException(status_code=404, detail=f"Agent '{requested}' not found")
        return body.get("body") or {}

    if _AGENT_PATH_RE.match(path):
        match = _AGENT_PATH_RE.match(path)
        assert match is not None
        if match.group("name") != "datahash_agent":
            raise HTTPException(status_code=404, detail=f"Agent '{match.group('name')}' not found")
        return body

    return body


def _copilotkit_sdk_version() -> str:
    try:
        import copilotkit

        return str(getattr(copilotkit, "COPILOTKIT_SDK_VERSION", "0.1.94"))
    except ImportError:
        return "0.1.94"


async def _handle_info(langgraph_agent) -> JSONResponse:
    sdk_version = _copilotkit_sdk_version()

    # CopilotKit v2 expects agents keyed by id, not a list.
    return JSONResponse(
        content={
            "version": sdk_version,
            "sdkVersion": sdk_version,
            "actions": [],
            "agents": {
                langgraph_agent.name: {
                    "name": langgraph_agent.name,
                    "description": langgraph_agent.description or "",
                    "type": "langgraph_agui",
                    "capabilities": {},
                }
            },
        }
    )


def _inject_session_context(run_body: dict[str, Any], session: Session) -> dict[str, Any]:
    """Merge authenticated user identity into the AG-UI state payload."""
    state = dict(run_body.get("state") or {})
    state.setdefault("customer_id", session.user_id)
    if session.username and not state.get("username"):
        state["username"] = session.username
    return {**run_body, "state": state}


async def _handle_agent_run(
    request: Request,
    langgraph_agent,
    body: dict[str, Any],
    *,
    path: str,
    session: Session,
):
    run_body = _inject_session_context(_extract_run_payload(body, path=path), session)
    try:
        input_data = RunAgentInput.model_validate(run_body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid run payload: {exc}") from exc

    accept_header = request.headers.get("accept") or "text/event-stream"
    encoder = EventEncoder(accept=accept_header)
    request_agent = langgraph_agent.clone()

    async def event_generator():
        async for event in request_agent.run(input_data):
            yield encoder.encode(event)

    return StreamingResponse(
        event_generator(),
        media_type=encoder.get_content_type(),
    )


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
)
async def copilotkit_endpoint(
    request: Request,
    path: str,
    session: Session = Depends(get_current_session),
    sdk=Depends(_get_sdk),
):
    """JWT-gated proxy into the CopilotKit / AG-UI runtime.

    Agent runs are streamed via :class:`copilotkit.LangGraphAGUIAgent` because
    that integration speaks AG-UI. Legacy CopilotKit execute routes are still
    delegated to the SDK handler for anything we do not recognise here.
    """
    langgraph_agent = _get_langgraph_agent(request)

    # Stash session bookkeeping on request.state so downstream code
    # can pull it from the runnable config.
    request.state.customer_id = session.user_id
    request.state.session_id = session.id

    logger.info(
        "copilotkit_request",
        path=path,
        method=request.method,
        user_id=session.user_id,
        session_id=session.id,
    )

    if request.method == "OPTIONS":
        return JSONResponse(content={})

    body: dict[str, Any] | None = None
    if request.method in ("POST", "PUT"):
        try:
            parsed = await request.json()
            body = parsed if isinstance(parsed, dict) else None
        except Exception:
            body = None

    if _is_info_request(body, path=path, method=request.method):
        return await _handle_info(langgraph_agent)

    if body and (
        body.get("method") in ("agent/run", "agent/connect")
        or (body.get("threadId") is not None and body.get("messages") is not None)
        or _AGENT_PATH_RE.match(path)
    ):
        return await _handle_agent_run(request, langgraph_agent, body, path=path, session=session)

    # Lazy import — avoid pulling the heavy copilotkit module on every cold start.
    from copilotkit.integrations.fastapi import handler as copilotkit_handler

    return await copilotkit_handler(request, sdk)
