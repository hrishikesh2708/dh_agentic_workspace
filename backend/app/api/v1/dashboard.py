"""Dashboard REST endpoints for the mapping-agent UI.

Routes are organised into three sub-paths:

- ``/mappings``       — mapping-session list / detail / delete.
- ``/golden-rules``   — learned golden-rule list / create / delete.
- ``/integrations``   — Salesforce OAuth status (Stage 4 stub).

All routes require JWT auth via :func:`app.api.v1.auth.get_current_user`.
"""

from typing import Optional
from urllib.parse import urlencode

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)

from app.api.v1.auth import get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.models.user import User
from app.schemas.dashboard.golden_rule import (
    GoldenRuleCreate,
    GoldenRuleListResponse,
    GoldenRuleRead,
)
from app.schemas.dashboard.integrations import (
    SalesforceOAuthCallback,
    SalesforceStatus,
)
from app.schemas.dashboard.mapping import (
    FieldMappingRead,
    MappingSessionDetail,
    MappingSessionListResponse,
    MappingSessionRead,
)
from app.services.mapping_dashboard import (
    create_golden_rule,
    delete_golden_rule,
    delete_user_mapping,
    get_user_mapping_detail,
    list_golden_rules,
    list_user_mappings,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# /mappings
# ---------------------------------------------------------------------------


@router.get("/mappings", response_model=MappingSessionListResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["mappings_list"][0])
async def list_mappings(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    kind: Optional[str] = Query(
        default=None,
        description="Optional mapping_kind filter: 'canonical' or 'projection'",
    ),
    user: User = Depends(get_current_user),
) -> MappingSessionListResponse:
    """List the current user's mapping sessions (paginated, summary only)."""
    if kind is not None and kind not in ("canonical", "projection"):
        raise HTTPException(
            status_code=422,
            detail="kind must be one of: canonical, projection",
        )

    logger.info(
        "mappings_list_requested",
        user_id=user.id,
        limit=limit,
        offset=offset,
        kind=kind,
    )

    rows, total = await list_user_mappings(
        user_id=user.id,
        limit=limit,
        offset=offset,
        kind=kind,
    )

    items = [MappingSessionRead.model_validate(row.model_dump()) for row in rows]
    return MappingSessionListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/mappings/{session_id}", response_model=MappingSessionDetail)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["mappings_detail"][0])
async def get_mapping_detail(
    request: Request,
    session_id: int,
    user: User = Depends(get_current_user),
) -> MappingSessionDetail:
    """Return a single mapping session with its nested field-mappings."""
    logger.info("mapping_detail_requested", user_id=user.id, session_id=session_id)

    detail = await get_user_mapping_detail(user_id=user.id, session_id=session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Mapping session not found")

    mapping_session, field_mappings = detail
    fm_reads = [FieldMappingRead.model_validate(fm.model_dump()) for fm in field_mappings]

    payload = mapping_session.model_dump()
    payload["field_mappings"] = fm_reads
    return MappingSessionDetail.model_validate(payload)


@router.delete("/mappings/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["mappings_detail"][0])
async def delete_mapping(
    request: Request,
    session_id: int,
    user: User = Depends(get_current_user),
) -> Response:
    """Delete a mapping session (and its field_mappings) owned by the user."""
    logger.info("mapping_delete_requested", user_id=user.id, session_id=session_id)

    deleted = await delete_user_mapping(user_id=user.id, session_id=session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Mapping session not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# /golden-rules
# ---------------------------------------------------------------------------


@router.get("/golden-rules", response_model=GoldenRuleListResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["golden_rules"][0])
async def list_rules(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    destination_type: Optional[str] = Query(
        default=None,
        description="Optional filter by destination schema id",
    ),
    user: User = Depends(get_current_user),
) -> GoldenRuleListResponse:
    """List golden rules sorted by occurrence_count desc (global, paginated)."""
    logger.info(
        "golden_rules_list_requested",
        user_id=user.id,
        limit=limit,
        offset=offset,
        destination_type=destination_type,
    )

    rows, total = await list_golden_rules(
        limit=limit,
        offset=offset,
        destination_type=destination_type,
    )
    items = [GoldenRuleRead.model_validate(row.model_dump()) for row in rows]
    return GoldenRuleListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/golden-rules",
    response_model=GoldenRuleRead,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["golden_rules"][0])
async def add_rule(
    request: Request,
    body: GoldenRuleCreate,
    user: User = Depends(get_current_user),
) -> GoldenRuleRead:
    """Manually create a golden rule."""
    logger.info(
        "golden_rule_create_requested",
        user_id=user.id,
        source_pattern=body.source_pattern,
        destination_field=body.destination_field,
        destination_type=body.destination_type,
    )

    rule = await create_golden_rule(
        source_pattern=body.source_pattern,
        destination_field=body.destination_field,
        destination_type=body.destination_type,
        occurrence_count=body.occurrence_count,
    )
    return GoldenRuleRead.model_validate(rule.model_dump())


@router.delete("/golden-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["golden_rules"][0])
async def remove_rule(
    request: Request,
    rule_id: int,
    user: User = Depends(get_current_user),
) -> Response:
    """Delete a golden rule by id."""
    logger.info("golden_rule_delete_requested", user_id=user.id, rule_id=rule_id)

    deleted = await delete_golden_rule(rule_id=rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Golden rule not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# /integrations/salesforce  (Stage 4 stub — real OAuth lives in Stage 7+)
# ---------------------------------------------------------------------------


def _build_salesforce_auth_url() -> str:
    """Construct the Salesforce OAuth authorise URL from settings."""
    base = settings.SALESFORCE_AUTH_URL.rstrip("/")
    params = {
        "response_type": "code",
        "client_id": settings.SALESFORCE_CLIENT_ID,
        "scope": "api refresh_token",
    }
    return f"{base}/services/oauth2/authorize?{urlencode(params)}"


@router.get("/integrations/salesforce/status", response_model=SalesforceStatus)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["integrations"][0])
async def salesforce_status(
    request: Request,
    user: User = Depends(get_current_user),
) -> SalesforceStatus:
    """Return the current user's Salesforce connection status (Stage 4 stub).

    Real OAuth is deferred to a later stage; this always reports
    ``connected=false`` and returns a generated authorise URL.
    """
    logger.info("salesforce_status_requested", user_id=user.id)

    return SalesforceStatus(
        connected=False,
        auth_url=_build_salesforce_auth_url(),
    )


@router.post("/integrations/salesforce/oauth/callback")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["integrations"][0])
async def salesforce_oauth_callback(
    request: Request,
    body: SalesforceOAuthCallback,
    user: User = Depends(get_current_user),
) -> dict:
    """Stage 4 stub: accept ``{code, state}`` without performing the OAuth exchange."""
    logger.info(
        "salesforce_oauth_callback_stubbed",
        user_id=user.id,
        has_state=body.state is not None,
    )

    return {
        "status": "stubbed",
        "todo": "implement Salesforce OAuth in a later stage",
    }
