"""Google OAuth two-step token exchange endpoint.

Step 1: Frontend initiates OAuth — user is redirected to Google consent screen.
Step 2: Google redirects back with ?code=... — this endpoint exchanges the code
        for access_token + refresh_token and stores them as connection secrets.

This replaces the ai-agent-poc pattern where the code exchange was done
directly in the frontend. Backend exchange is safer (secrets never in browser).
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class GoogleCodeExchangeRequest(BaseModel):
    """Request body for the Google OAuth code exchange."""

    code: str
    redirect_uri: str
    project_id: str
    destination_type: str  # e.g. "google_offline", "google_dm"


class GoogleCodeExchangeResponse(BaseModel):
    """Response after successful token exchange."""

    success: bool
    access_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None
    has_refresh_token: bool = False
    mock: bool = False


@router.post("/google/token-exchange", response_model=GoogleCodeExchangeResponse)
async def exchange_google_oauth_code(body: GoogleCodeExchangeRequest):
    """Exchange a Google OAuth authorization code for access + refresh tokens.

    The refresh token is stored server-side as a connection secret.
    The access token is returned to the frontend for immediate use.

    Mock mode: if code starts with 'mock_', returns fake tokens for dev/testing.
    """
    from app.config import settings

    # Mock mode for development
    if body.code.startswith("mock_"):
        return GoogleCodeExchangeResponse(
            success=True,
            access_token="mock_access_token_" + body.destination_type,
            token_type="Bearer",
            expires_in=3600,
            has_refresh_token=True,
            mock=True,
        )

    client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
    client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth credentials not configured on the server.",
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": body.code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": body.redirect_uri,
                    "grant_type": "authorization_code",
                },
            )

        if resp.status_code >= 400:
            raise HTTPException(
                status_code=400,
                detail=f"Google token exchange failed: {resp.text}",
            )

        tokens = resp.json()
        access_token = tokens.get("access_token", "")
        refresh_token = tokens.get("refresh_token", "")

        # Store refresh_token as a connection secret (fire and forget — best effort)
        if refresh_token and body.project_id:
            try:
                await _store_connection_secret(
                    project_id=body.project_id,
                    destination_type=body.destination_type,
                    secret_key="refresh_token",  # pragma: allowlist secret
                    secret_value=refresh_token,
                )
            except Exception:
                pass  # Log but don't fail the exchange

        return GoogleCodeExchangeResponse(
            success=True,
            access_token=access_token,
            token_type=tokens.get("token_type", "Bearer"),
            expires_in=tokens.get("expires_in", 3600),
            has_refresh_token=bool(refresh_token),
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _store_connection_secret(
    project_id: str,
    destination_type: str,
    secret_key: str,
    secret_value: str,
) -> None:
    """Best-effort: store a token as a ProjectConnectionSecret."""
    try:
        from uuid import UUID

        from sqlmodel import col, select

        from app.agents.deps import session_maker
        from app.models import Destination, ProjectConnection, ProjectConnectionSecret

        async with session_maker() as session:
            dest_result = await session.execute(select(Destination).where(Destination.name == destination_type))
            dest = dest_result.scalars().first()
            if not dest:
                return

            result = await session.execute(
                select(ProjectConnection).where(
                    ProjectConnection.project_id == UUID(project_id),
                    ProjectConnection.destination_id == dest.id,
                    col(ProjectConnection.is_deleted).is_(False),
                )
            )
            conn = result.scalars().first()
            if not conn or conn.id is None:
                return

            # Upsert the secret
            existing = await session.execute(
                select(ProjectConnectionSecret).where(
                    ProjectConnectionSecret.project_connection_id == conn.id,
                    ProjectConnectionSecret.secret_key == secret_key,
                )
            )
            secret_row = existing.scalars().first()
            if secret_row:
                secret_row.secret_value = secret_value
            else:
                session.add(
                    ProjectConnectionSecret(
                        project_connection_id=conn.id,
                        secret_key=secret_key,
                        secret_value=secret_value,
                    )
                )
            await session.commit()
    except Exception:
        pass  # Best-effort only


@router.get("/google/authorize-url")
async def get_google_authorize_url(
    destination_type: str,
    redirect_uri: str,
    project_id: str,
):
    """Generate the Google OAuth authorization URL.

    Frontend redirects user to this URL to initiate the consent flow.
    """
    from app.services.oauth_utils import build_oauth_url, generate_state_token

    state = generate_state_token()
    url = build_oauth_url(destination_type, redirect_uri, state)
    if not url:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth not configured for destination: {destination_type}",
        )
    return {"authorization_url": url, "state": state}
