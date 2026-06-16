"""Project workspace endpoints for Copilot project context."""

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)

from app.api.v1.auth import get_current_user
from app.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.models import User
from app.schemas import (
    ProjectCreate,
    ProjectListResponse,
    ProjectRead,
)
from app.services.project import (
    create_user_project,
    get_user_project,
    list_user_projects,
)

router = APIRouter()


@router.get("", response_model=ProjectListResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["projects"][0])
async def list_projects(
    request: Request,
    user: User = Depends(get_current_user),
) -> ProjectListResponse:
    """List all project workspaces owned by the current user."""
    projects = list_user_projects(user.id)
    items = [ProjectRead.model_validate(p) for p in projects]
    logger.info("projects_listed", user_id=user.id, total=len(items))
    return ProjectListResponse(items=items, total=len(items))


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["projects"][0])
async def create_project(
    request: Request,
    body: ProjectCreate,
    user: User = Depends(get_current_user),
) -> ProjectRead:
    """Create a new project workspace for the current user."""
    project = create_user_project(
        user.id,
        name=body.name,
        description=body.description,
    )
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectRead)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["projects"][0])
async def get_project(
    request: Request,
    project_id: UUID,
    user: User = Depends(get_current_user),
) -> ProjectRead:
    """Return one project if it belongs to the current user."""
    project = get_user_project(user.id, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRead.model_validate(project)
