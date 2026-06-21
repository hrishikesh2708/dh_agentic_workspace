"""OAuth connection endpoints — initiate and callback for all connectors.

Flow:
    1. Frontend calls POST /connections/{connector_slug}/authorize?project_id=X
       → backend generates PKCE pair, inserts OAuthPending, returns {auth_url}
    2. Frontend opens auth_url in popup/redirect
    3. Provider redirects to GET /connections/{connector_slug}/callback?code=...&state=...
       → backend exchanges code, writes ProjectConnection + ProjectConnectionSecret,
         deletes OAuthPending row, returns {success: true}
    4. Frontend closes popup and resumes the agent thread

Supported connectors and their auth_scheme (from the ``connector`` table):
    - salesforce  → oauth2 (Authorization Code + PKCE)
    - meta_capi   → oauth2
    - google_ads  → oauth2
    - tiktok      → oauth2
    - snapchat    → oauth2

All token secrets go into ProjectConnectionSecret rows.
Non-secret account identifiers go into ProjectConnection.connection_metadata.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.api.v1.auth import get_current_user
from app.config import settings
from app.core.logging import logger
from app.models import Destination
from app.models import OAuthPending
from app.models import Project
from app.models import ProjectConnection, ProjectConnectionStatus, ProjectConnectionType
from app.models import ProjectConnectionSecret
from app.models import Source
from app.models import User
from app.services.database import database_service

router = APIRouter()

# ---------------------------------------------------------------------------
# Per-connector OAuth configuration
# ---------------------------------------------------------------------------


# Maps parent platform slug → canonical OAuth config key.
# Sub-connectors (e.g. "meta_conversions_api_crm") inherit the parent platform's
# OAuth app, so we resolve them to the parent's config key at auth time.
_PARENT_TO_OAUTH_KEY: dict[str, str] = {
    "meta": "meta_capi",
    "google": "google_ads",
}


def _canonical_oauth_slug(connector_slug: str) -> str:
    """Map a destination/source name to its OAuth config key.

    Most names map to themselves; exceptions are listed in _PARENT_TO_OAUTH_KEY.
    """
    return _PARENT_TO_OAUTH_KEY.get(connector_slug, connector_slug)


def _get_connector_oauth_config(connector_slug: str) -> dict[str, str]:
    """Return OAuth endpoints and client credentials for a connector."""
    configs: dict[str, dict[str, str]] = {
        "salesforce": {
            "authorize_url": f"{settings.SALESFORCE_AUTH_URL}/services/oauth2/authorize",
            "token_url": f"{settings.SALESFORCE_AUTH_URL}/services/oauth2/token",
            "client_id": settings.SALESFORCE_CLIENT_ID,
            "client_secret": settings.SALESFORCE_CLIENT_SECRET,
        },
        "meta_capi": {
            "authorize_url": "https://www.facebook.com/v21.0/dialog/oauth",
            "token_url": "https://graph.facebook.com/v21.0/oauth/access_token",
            "client_id": settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
        },
        "google_ads": {
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
        },
        "tiktok": {
            "authorize_url": "https://www.tiktok.com/v2/auth/authorize/",
            "token_url": "https://open.tiktokapis.com/v2/oauth/token/",
            "client_id": settings.TIKTOK_APP_ID,
            "client_secret": settings.TIKTOK_APP_SECRET,
        },
        "snapchat": {
            "authorize_url": "https://accounts.snapchat.com/login/oauth2/authorize",
            "token_url": "https://accounts.snapchat.com/login/oauth2/access_token",
            "client_id": settings.SNAPCHAT_CLIENT_ID,
            "client_secret": settings.SNAPCHAT_CLIENT_SECRET,
        },
    }
    cfg = configs.get(connector_slug)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Connector '{connector_slug}' not supported for OAuth")
    return cfg


def _callback_url(request: Request, connector_slug: str) -> str:
    base = settings.OAUTH_CALLBACK_BASE_URL.rstrip("/")
    return f"{base}/api/v1/connections/{connector_slug}/callback"


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------


def _pkce_pair() -> tuple[str, str]:
    """Return (verifier, challenge). Challenge is S256-hashed verifier."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    import base64

    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _get_engine():
    return database_service.engine


def _assert_project_owned(db: Session, project_id: UUID, user_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _resolve_connection_ids(connector_slug: str, db: Session) -> tuple[ProjectConnectionType, int | None, int | None]:
    """Resolve a name to (connection_type, source_id, destination_id).

    Tries Source first, then Destination. Both tables use ``name`` as the
    human-readable slug (e.g. "salesforce", "meta", "google").
    """
    src = db.exec(select(Source).where(Source.name == connector_slug)).first()
    if src:
        return ProjectConnectionType.source, src.id, None

    dest = db.exec(select(Destination).where(Destination.name == connector_slug)).first()
    if dest:
        return ProjectConnectionType.destination, None, dest.id

    raise HTTPException(status_code=404, detail=f"No source or destination found with name '{connector_slug}'")


def _upsert_connection(
    db: Session,
    *,
    project_id: UUID,
    connector_slug: str,
    metadata: dict[str, Any],
) -> ProjectConnection:
    """Insert or update a ProjectConnection row, return it."""
    conn_type, source_id, destination_id = _resolve_connection_ids(connector_slug, db)

    if source_id is not None:
        stmt = select(ProjectConnection).where(
            ProjectConnection.project_id == project_id,
            ProjectConnection.source_id == source_id,
        )
    else:
        stmt = select(ProjectConnection).where(
            ProjectConnection.project_id == project_id,
            ProjectConnection.destination_id == destination_id,
        )
    conn = db.exec(stmt).first()
    if conn:
        conn.status = ProjectConnectionStatus.active
        conn.connection_metadata = metadata
        conn.is_deleted = False
    else:
        conn = ProjectConnection(
            project_id=project_id,
            connection_type=conn_type,
            source_id=source_id,
            destination_id=destination_id,
            status=ProjectConnectionStatus.active,
            connection_metadata=metadata,
        )
        db.add(conn)
    db.flush()
    return conn


def _upsert_secret(db: Session, *, connection_id: UUID, key: str, value: str) -> None:
    """Insert or update a single ProjectConnectionSecret row."""
    stmt = select(ProjectConnectionSecret).where(
        ProjectConnectionSecret.project_connection_id == connection_id,
        ProjectConnectionSecret.secret_key == key,
    )
    secret = db.exec(stmt).first()
    if secret:
        secret.secret_value = value
    else:
        secret = ProjectConnectionSecret(
            project_connection_id=connection_id,
            secret_key=key,
            secret_value=value,
        )
        db.add(secret)


# ---------------------------------------------------------------------------
# Authorize endpoint
# ---------------------------------------------------------------------------


class AuthorizeResponse(BaseModel):
    """OAuth authorize endpoint response."""

    auth_url: str
    state: str


@router.post("/{connector_slug}/authorize", response_model=AuthorizeResponse)
async def authorize(
    request: Request,
    connector_slug: str,
    project_id: UUID = Query(...),
    user: User = Depends(get_current_user),
):
    """Generate an OAuth authorization URL for the given connector.

    Inserts an OAuthPending row with the PKCE verifier, then returns
    the provider authorization URL for the frontend to open.
    """
    verifier, challenge = _pkce_pair()
    state_token = secrets.token_urlsafe(32)
    redirect_uri = _callback_url(request, connector_slug)

    with _get_engine().begin() as conn_raw:
        with Session(conn_raw) as db:
            _assert_project_owned(db, project_id, user.id)

            oauth_slug = _canonical_oauth_slug(connector_slug)

            cfg = _get_connector_oauth_config(oauth_slug)

            conn_type, source_id, destination_id = _resolve_connection_ids(connector_slug, db)
            pending = OAuthPending(
                state=state_token,
                project_id=project_id,
                session_id=request.headers.get("x-session-id", ""),
                connection_type=conn_type,
                source_id=source_id,
                destination_id=destination_id,
                pkce_verifier=verifier,
            )
            db.add(pending)
            db.commit()

    # Build provider auth URL
    params = {
        "response_type": "code",
        "client_id": cfg["client_id"],
        "redirect_uri": redirect_uri,
        "state": state_token,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }

    # Connector-specific scope overrides — keyed by oauth_slug (canonical platform key)
    scopes: dict[str, str] = {
        "salesforce": "api refresh_token offline_access",
        "meta_capi": "ads_management,business_management",
        "google_ads": "https://www.googleapis.com/auth/adwords",
        "tiktok": "user.info.basic,pixel.management",
        "snapchat": "snapchat-marketing-api",
    }
    if oauth_slug in scopes:
        params["scope"] = scopes[oauth_slug]

    # Google requires these to receive a refresh_token; without them the token
    # response omits refresh_token entirely and the connection breaks after 1h.
    if oauth_slug == "google_ads":
        params["access_type"] = "offline"
        params["prompt"] = "consent"

    import urllib.parse

    auth_url = cfg["authorize_url"] + "?" + urllib.parse.urlencode(params)

    logger.info(
        "oauth_authorize_initiated",
        connector_slug=connector_slug,
        project_id=str(project_id),
        redirect_uri=redirect_uri,  # ← log so you can copy-paste into provider app settings
    )
    return AuthorizeResponse(auth_url=auth_url, state=state_token)


# ---------------------------------------------------------------------------
# Callback endpoint
# ---------------------------------------------------------------------------


@router.get("/{connector_slug}/callback")
async def callback(
    request: Request,
    connector_slug: str,
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(default=None),
):
    """OAuth callback — exchange code for tokens, persist connection, close popup."""
    if error:
        logger.warning("oauth_callback_error", connector_slug=connector_slug, error=error)
        return _popup_close_response(success=False, error=error)

    redirect_uri = _callback_url(request, connector_slug)

    with _get_engine().begin() as conn_raw:
        with Session(conn_raw) as db:
            # Look up pending row and verify it belongs to this connector
            pending = db.get(OAuthPending, state)
            if not pending:
                raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
            # Re-resolve the incoming connector_slug to ids and confirm they match the pending row
            _, expected_source_id, expected_dest_id = _resolve_connection_ids(connector_slug, db)
            if pending.source_id != expected_source_id or pending.destination_id != expected_dest_id:
                raise HTTPException(status_code=400, detail="OAuth state does not match connector")

            project_id = pending.project_id
            verifier = pending.pkce_verifier

            oauth_slug = _canonical_oauth_slug(connector_slug)
            cfg = _get_connector_oauth_config(oauth_slug)

            # Exchange code for tokens
            try:
                token_data = await _exchange_code(
                    cfg=cfg,
                    code=code,
                    redirect_uri=redirect_uri,
                    verifier=verifier,
                )
            except Exception as exc:
                logger.error("oauth_token_exchange_failed", connector_slug=connector_slug, error=str(exc))
                db.delete(pending)
                db.commit()
                return _popup_close_response(success=False, error="Token exchange failed")

            # Extract secrets vs metadata per connector (use oauth_slug for platform branching)
            secrets_map, metadata = _parse_token_response(oauth_slug, token_data)

            # Persist connection
            conn_obj = _upsert_connection(
                db,
                project_id=project_id,
                connector_slug=connector_slug,
                metadata=metadata,
            )
            if conn_obj.id is None:
                raise RuntimeError("ProjectConnection id missing after upsert")
            for key, value in secrets_map.items():
                _upsert_secret(db, connection_id=conn_obj.id, key=key, value=value)

            # Clean up pending row
            db.delete(pending)
            db.commit()

    logger.info("oauth_connection_saved", connector_slug=connector_slug, project_id=str(project_id))
    return _popup_close_response(success=True, connector_slug=connector_slug)


# ---------------------------------------------------------------------------
# Connection status endpoint (used by agent and frontend)
# ---------------------------------------------------------------------------


@router.get("/{connector_slug}/status")
async def connection_status(
    connector_slug: str,
    project_id: UUID = Query(...),
    user: User = Depends(get_current_user),
):
    """Return whether an active connection exists for this project + connector."""
    with _get_engine().begin() as conn_raw:
        with Session(conn_raw) as db:
            _assert_project_owned(db, project_id, user.id)
            _, source_id, destination_id = _resolve_connection_ids(connector_slug, db)
            if source_id is not None:
                filter_col = ProjectConnection.source_id == source_id
            else:
                filter_col = ProjectConnection.destination_id == destination_id
            stmt = select(ProjectConnection).where(
                ProjectConnection.project_id == project_id,
                ProjectConnection.status == ProjectConnectionStatus.active,
                col(ProjectConnection.is_deleted).is_(False),
                filter_col,
            )
            conn_obj = db.exec(stmt).first()

    metadata = conn_obj.connection_metadata or {} if conn_obj else {}
    return {
        "connected": conn_obj is not None,
        "connector_slug": connector_slug,
        "account_detail": metadata.get("instance_url") or metadata.get("account_name"),
    }


# ---------------------------------------------------------------------------
# DEBUG: fake connection (dev only)
# ---------------------------------------------------------------------------


@router.post("/{connector_slug}/debug-connect")
async def debug_connect(
    connector_slug: str,
    project_id: UUID = Query(...),
    user: User = Depends(get_current_user),
):
    """[DEBUG] Insert a fake active ProjectConnection without going through OAuth.

    Useful for local development to test downstream agent steps (mapping, etc.)
    without needing real OAuth credentials.
    """
    with _get_engine().begin() as conn_raw:
        with Session(conn_raw) as db:
            _assert_project_owned(db, project_id, user.id)

            _upsert_connection(
                db,
                project_id=project_id,
                connector_slug=connector_slug,
                metadata={"debug": True, "instance_url": f"https://debug.{connector_slug}.local"},
            )
            db.commit()

    logger.warning(
        "debug_fake_connection_created",
        connector_slug=connector_slug,
        project_id=str(project_id),
    )
    return {"connected": True, "connector_slug": connector_slug, "debug": True}


# ---------------------------------------------------------------------------
# DEBUG: delete connection (dev only)
# ---------------------------------------------------------------------------


@router.delete("/{connector_slug}/disconnect")
async def disconnect(
    connector_slug: str,
    project_id: UUID = Query(...),
    user: User = Depends(get_current_user),
):
    """[DEBUG] Hard-delete all connection rows for this project + connector.

    Intended for local development only — lets you reset OAuth state without
    touching the database manually.
    """
    with _get_engine().begin() as conn_raw:
        with Session(conn_raw) as db:
            _assert_project_owned(db, project_id, user.id)
            _, source_id, destination_id = _resolve_connection_ids(connector_slug, db)
            if source_id is not None:
                filter_col = ProjectConnection.source_id == source_id
            else:
                filter_col = ProjectConnection.destination_id == destination_id
            stmt = select(ProjectConnection).where(
                ProjectConnection.project_id == project_id,
                filter_col,
            )
            rows = db.exec(stmt).all()
            for row in rows:
                # cascade deletes secrets if FK + ondelete=CASCADE is set,
                # otherwise delete secrets explicitly first
                secret_stmt = select(ProjectConnectionSecret).where(
                    ProjectConnectionSecret.project_connection_id == row.id
                )
                for secret in db.exec(secret_stmt).all():
                    db.delete(secret)
                db.delete(row)
            db.commit()

    logger.warning(
        "debug_disconnect",
        connector_slug=connector_slug,
        project_id=str(project_id),
        deleted=len(rows),
    )
    return {"deleted": len(rows), "connector_slug": connector_slug}


# ---------------------------------------------------------------------------
# Token exchange helpers
# ---------------------------------------------------------------------------


async def _exchange_code(
    *,
    cfg: dict[str, str],
    code: str,
    redirect_uri: str,
    verifier: str | None,
) -> dict[str, Any]:
    payload: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
    }
    if verifier:
        payload["code_verifier"] = verifier

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(cfg["token_url"], data=payload)
        resp.raise_for_status()
        return resp.json()


def _parse_token_response(connector_slug: str, data: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    """Split token response into (secrets, metadata) for the given connector."""
    secrets_map: dict[str, str] = {}
    metadata: dict[str, Any] = {}

    if connector_slug == "salesforce":
        secrets_map["access_token"] = data["access_token"]
        if data.get("refresh_token"):
            secrets_map["refresh_token"] = data["refresh_token"]
        metadata["instance_url"] = data.get("instance_url", "")

    elif connector_slug == "meta_capi":
        secrets_map["access_token"] = data["access_token"]
        # pixel_id / dataset_id are supplied by the user separately; stored in metadata later
        metadata["token_type"] = data.get("token_type", "bearer")

    elif connector_slug == "google_ads":
        secrets_map["access_token"] = data["access_token"]
        if data.get("refresh_token"):
            secrets_map["refresh_token"] = data["refresh_token"]
        metadata["scope"] = data.get("scope", "")

    elif connector_slug == "tiktok":
        inner = data.get("data", data)
        secrets_map["access_token"] = inner.get("access_token", "")
        if inner.get("refresh_token"):
            secrets_map["refresh_token"] = inner["refresh_token"]
        metadata["advertiser_id"] = inner.get("advertiser_id", "")

    elif connector_slug == "snapchat":
        secrets_map["access_token"] = data["access_token"]
        if data.get("refresh_token"):
            secrets_map["refresh_token"] = data["refresh_token"]
        metadata["token_type"] = data.get("token_type", "bearer")

    else:
        # Generic fallback
        if data.get("access_token"):
            secrets_map["access_token"] = data["access_token"]
        if data.get("refresh_token"):
            secrets_map["refresh_token"] = data["refresh_token"]

    return secrets_map, metadata


# ---------------------------------------------------------------------------
# Popup close helper
# ---------------------------------------------------------------------------


def _popup_close_response(*, success: bool, connector_slug: str = "", error: str = "") -> HTMLResponse:
    """Return an HTML page that posts a message to the opener and closes itself."""
    payload = json.dumps(
        {"type": "oauth_complete", "success": success, "connector_slug": connector_slug, "error": error}
    )
    html = f"""<!DOCTYPE html>
<html>
<body>
<script>
  if (window.opener) {{
    window.opener.postMessage({payload}, '*');
  }}
  window.close();
</script>
</body>
</html>"""
    return HTMLResponse(content=html)
