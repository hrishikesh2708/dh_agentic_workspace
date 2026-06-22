"""API v1 router configuration."""

from fastapi import APIRouter

from app.agents.routes import router as copilotkit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.connections import router as connections_router
from app.api.v1.oauth_exchange import router as oauth_exchange_router
from app.api.v1.projects import router as projects_router
from app.api.v1.sync import router as sync_router
from app.api.v1.google_ads import router as google_ads_router
from app.api.v1.schemas import router as schemas_router
from app.core.logging import logger

api_router = APIRouter()

# Include routers
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(copilotkit_router, prefix="/copilotkit", tags=["agent"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(connections_router, prefix="/connections", tags=["connections"])
api_router.include_router(oauth_exchange_router, prefix="/connections", tags=["oauth"])
api_router.include_router(sync_router, prefix="/sync", tags=["sync"])
api_router.include_router(google_ads_router, prefix="/connections", tags=["google-ads"])
api_router.include_router(schemas_router, prefix="/schemas", tags=["schemas"])


@api_router.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        dict: Health status information.
    """
    logger.info("health_check_called")
    return {"status": "healthy", "version": "1.0.0"}
