"""Sync runner endpoints.

LEVEL 1 (current): Credential dry-run — validates stored OAuth tokens for each
active destination without reading any real Salesforce data.

TODO Level 2: One-shot single-record sync — read one real SF record, transform
through field mappings, send to each destination.

TODO Level 3: Scheduled poller — Celery/APScheduler job with watermark-based
SF polling, batched sends, and sync-state tracking in DB.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.models import User
from app.services.sync_runner import dry_run_project

router = APIRouter()


async def _get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session."""
    from app.agents.deps import session_maker

    async with session_maker() as session:
        yield session


@router.post(
    "/dry-run/{project_id}",
    summary="Credential dry-run for all active integrations in a project",
    status_code=status.HTTP_200_OK,
)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS.get("sync", ["10 per minute"])[0])
async def dry_run_sync(
    request: Request,
    project_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(_get_session),
):
    """Validate stored credentials for every active destination in the project.

    Sends a synthetic test event to Meta CAPI and a token-check call to Google.
    No real Salesforce data is read or transformed.

    Returns a list of per-destination results:
    ```json
    {
      "project_id": "...",
      "results": [
        { "destination": "meta_capi", "display_name": "Meta Conversions API",
          "passed": true, "message": "Meta test event accepted." }
      ],
      "all_passed": true
    }
    ```
    """
    logger.info("dry_run_sync_triggered", project_id=str(project_id), user_id=user.id)

    try:
        results = await dry_run_project(project_id, session)
    except Exception as exc:
        logger.exception("dry_run_sync_failed", project_id=str(project_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dry-run failed: {exc}",
        ) from exc

    all_passed = all(r["passed"] for r in results)

    return {
        "project_id": str(project_id),
        "results": results,
        "all_passed": all_passed,
    }
