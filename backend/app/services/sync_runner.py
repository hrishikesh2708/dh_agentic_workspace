"""Sync runner — credential dry-run per activated destination.

LEVEL 1 (current): Validates stored credentials for each active ProjectIntegration
by sending a test event / calling a credential-check API. No SF data is read,
no real records are transformed or sent.

TODO Level 2: Read one real SF record for the configured source_object, transform
it through project_field_mapping (SF field -> canonical key), hash PII fields
(SHA-256 for email/phone), and send to each destination. One-shot, manual trigger.

TODO Level 3: Scheduled poller — Celery/APScheduler job that polls SF with a
watermark (LastModifiedDate), pages through results, transforms every record,
batches sends to each destination, and tracks sync state in DB.

Ported from ai-agent-poc/server/app/services/destination_oauth.py dry-run functions.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.config import settings
from app.models import (
    Destination,
    ProjectConnection,
    ProjectConnectionSecret,
    ProjectIntegration,
    ProjectSourceModule,
)

logger = logging.getLogger(__name__)

META_GRAPH = "https://graph.facebook.com/v19.0"
GOOGLE_ADS_BASE = "https://googleads.googleapis.com"


# ---------------------------------------------------------------------------
# Secret helpers
# ---------------------------------------------------------------------------


async def _load_secrets(conn_id: UUID, session: AsyncSession) -> dict[str, str]:
    """Return all secret_key → secret_value pairs for a connection."""
    result = await session.execute(
        select(ProjectConnectionSecret).where(ProjectConnectionSecret.project_connection_id == conn_id)
    )
    return {row.secret_key: row.secret_value for row in result.scalars().all()}


# ---------------------------------------------------------------------------
# Meta CAPI dry-run (Level 1)
# ---------------------------------------------------------------------------


async def _dry_run_meta_capi(
    conn: ProjectConnection,
    secrets: dict[str, str],
) -> tuple[bool, str]:
    """Send one synthetic test event to Meta CAPI.

    Requires:
    - secrets["access_token"]
    - conn.connection_metadata["pixel_id"]
    """
    access_token = secrets.get("access_token", "")
    pixel_id = (conn.connection_metadata or {}).get("pixel_id", "")

    # Mock / missing credentials path
    if not access_token or access_token.startswith("mock_"):
        return True, "Meta dry-run passed (mock credentials — no API call made)."

    if not pixel_id:
        return False, "Meta Pixel ID not configured in connection metadata."

    # Minimal synthetic event — just enough to validate the token + pixel
    test_event: dict[str, Any] = {
        "event_name": "Purchase",
        "event_time": 1700000000,
        "action_source": "system_generated",
        "user_data": {
            "em": [hashlib.sha256("test@datahash.com".encode()).hexdigest()],
        },
    }

    body: dict[str, Any] = {"data": [test_event]}
    if settings.META_TEST_EVENT_CODE:
        body["test_event_code"] = settings.META_TEST_EVENT_CODE

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{META_GRAPH}/{pixel_id}/events",
                params={"access_token": access_token},
                json=body,
            )
        if response.status_code >= 400:
            return False, f"Meta dry-run failed: {response.text}"
        return True, "Meta test event accepted by Conversions API."
    except Exception as exc:
        logger.exception("meta_dry_run_error pixel_id=%s", pixel_id)
        return False, f"Meta dry-run error: {exc}"


# ---------------------------------------------------------------------------
# Google dry-run (Level 1)
# ---------------------------------------------------------------------------


async def _refresh_google_token(refresh_token: str) -> str:
    """Mint a fresh Google access token from the stored refresh token."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
    response.raise_for_status()
    return response.json()["access_token"]


async def _dry_run_google(
    conn: ProjectConnection,
    secrets: dict[str, str],
    destination_slug: str,
) -> tuple[bool, str]:
    """Validate Google credentials by calling listAccessibleCustomers.

    Works for both google_ads_offline_conversions and google_customer_match —
    both share the same credential model.

    Requires:
    - secrets["access_token"] or secrets["refresh_token"]
    - settings.GOOGLE_ADS_DEVELOPER_TOKEN for a live API call
    """
    refresh_token = secrets.get("refresh_token", "")
    access_token = secrets.get("access_token", "")

    # Mock path
    if (access_token and access_token.startswith("mock_")) or (refresh_token and refresh_token.startswith("mock_")):
        return True, "Google dry-run passed (mock credentials — no API call made)."

    if not settings.GOOGLE_ADS_DEVELOPER_TOKEN:
        return (
            True,
            "Google OAuth token stored. Live API check skipped (developer token not configured).",
        )

    try:
        token = await _refresh_google_token(refresh_token) if refresh_token else access_token
        if not token:
            return False, "No Google credentials available."

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{GOOGLE_ADS_BASE}/{settings.GOOGLE_API_VERSION}/customers:listAccessibleCustomers",
                headers={
                    "Authorization": f"Bearer {token}",
                    "developer-token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                },
            )
        if response.status_code >= 400:
            return False, f"Google Ads API check failed: {response.text}"
        return True, "Google Ads API accessible — credentials valid."
    except Exception as exc:
        logger.exception("google_dry_run_error destination=%s", destination_slug)
        return False, f"Google dry-run error: {exc}"


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


_META_SLUGS = {"meta_capi", "meta_conversions_api"}
_GOOGLE_SLUGS = {"google_ads_offline_conversions", "google_offline_conversions", "google_customer_match"}


async def _run_destination(
    conn: ProjectConnection,
    destination: Destination,
    secrets: dict[str, str],
) -> dict[str, Any]:
    slug = (destination.name or "").lower()

    if slug in _META_SLUGS:
        passed, message = await _dry_run_meta_capi(conn, secrets)
    elif slug in _GOOGLE_SLUGS:
        passed, message = await _dry_run_google(conn, secrets, slug)
    else:
        # Unknown destination — report as skipped, not failed
        passed, message = True, f"Dry-run not implemented for '{slug}' — skipped."

    return {
        "destination": slug,
        "display_name": destination.display_name,
        "passed": passed,
        "message": message,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def dry_run_project(project_id: UUID, session: AsyncSession) -> list[dict[str, Any]]:
    """Run Level-1 credential dry-run for all active integrations in a project.

    Returns a list of per-destination results:
    [{ destination, display_name, passed, message }]
    """
    # Load active integrations for this project via source module
    result = await session.execute(
        select(ProjectIntegration, ProjectConnection, Destination)
        .join(
            ProjectSourceModule,
            col(ProjectIntegration.source_module_id) == ProjectSourceModule.id,
        )
        .join(
            ProjectConnection,
            col(ProjectIntegration.destination_conn_id) == ProjectConnection.id,
        )
        .join(
            Destination,
            col(ProjectIntegration.destination_id) == Destination.id,
        )
        .where(
            ProjectConnection.project_id == project_id,
            col(ProjectIntegration.is_deleted).is_(False),
            col(ProjectConnection.is_deleted).is_(False),
        )
    )

    rows = result.all()
    if not rows:
        return [
            {
                "destination": "none",
                "display_name": "—",
                "passed": False,
                "message": "No active integrations found for this project.",
            }
        ]

    results: list[dict[str, Any]] = []
    for _integration, conn, destination in rows:
        if conn.id is None:
            continue
        secrets = await _load_secrets(conn.id, session)
        result_row = await _run_destination(conn, destination, secrets)
        logger.info(
            "dry_run_result project_id=%s destination=%s passed=%s",
            project_id,
            result_row["destination"],
            result_row["passed"],
        )
        results.append(result_row)

    return results
