"""Main application entry point."""

from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import quote_plus

from dotenv import load_dotenv
from fastapi import (
    FastAPI,
    Request,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg import AsyncConnection
from psycopg.rows import (
    DictRow,
    dict_row,
)
from psycopg_pool import AsyncConnectionPool
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from asgi_correlation_id import CorrelationIdMiddleware

from app.api.v1.api import api_router
from app.core.cache import cache_service
from app.core.config import (
    Environment,
    settings,
)
from app.core.limiter import limiter
from app.core.logging import logger
from app.core.metrics import setup_metrics
from app.core.middleware import (
    LoggingContextMiddleware,
    MetricsMiddleware,
    ProfilingMiddleware,
)
from app.core.observability import langsmith_init
from app.services.database import database_service

# Load environment variables
load_dotenv()
langsmith_init()

# Module-level connection pool owned by main — shared with the datahash agent checkpointer
_agent_conn_pool: AsyncConnectionPool[AsyncConnection[DictRow]] | None = None


async def _create_agent_pool() -> AsyncConnectionPool[AsyncConnection[DictRow]] | None:
    """Create the psycopg connection pool used by the datahash agent's Postgres checkpointer."""
    try:
        connection_url = (
            "postgresql://"
            f"{quote_plus(settings.POSTGRES_USER)}:{quote_plus(settings.POSTGRES_PASSWORD)}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )
        pool: AsyncConnectionPool[AsyncConnection[DictRow]] = AsyncConnectionPool(
            connection_url,
            open=False,
            max_size=settings.POSTGRES_POOL_SIZE,
            kwargs={
                "autocommit": True,
                "connect_timeout": 5,
                "prepare_threshold": None,
                "row_factory": dict_row,
            },
        )
        await pool.open()
        logger.info("agent_connection_pool_created", max_size=settings.POSTGRES_POOL_SIZE)
        return pool
    except Exception as e:
        logger.error("agent_connection_pool_failed", error=str(e))
        if settings.ENVIRONMENT == Environment.PRODUCTION:
            logger.warning("continuing_without_agent_connection_pool")
            return None
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    global _agent_conn_pool

    logger.info(
        "application_startup",
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        api_prefix=settings.API_V1_STR,
    )

    # Initialize cache service (connects to Valkey if configured)
    try:
        await cache_service.initialize()
    except Exception as e:
        logger.exception("cache_initialization_failed", error=str(e))

    # Build the datahash mapping agent + wrap as CopilotKit SDK
    # so /api/v1/copilotkit serves the AG-UI protocol.
    try:
        from copilotkit import (
            CopilotKitRemoteEndpoint,
            LangGraphAGUIAgent,
        )
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        from app.agents import build_app_graph

        _agent_conn_pool = await _create_agent_pool()
        if _agent_conn_pool:
            checkpointer = AsyncPostgresSaver(_agent_conn_pool)
            await checkpointer.setup()
        else:
            checkpointer = None

        mapping_graph = build_app_graph(checkpointer)
        ck_agent = LangGraphAGUIAgent(name="datahash_agent", graph=mapping_graph)
        app.state.langgraph_agent = ck_agent
        app.state.copilotkit_sdk = CopilotKitRemoteEndpoint(agents=[ck_agent])  # pyright: ignore[reportArgumentType]
        logger.info(
            "datahash_agent_initialized",
            agent_name="datahash_agent",
            has_checkpointer=checkpointer is not None,
        )
    except Exception as e:
        logger.exception("datahash_agent_init_failed", error=str(e))

    yield

    # Cleanup on shutdown
    await cache_service.close()
    if _agent_conn_pool:
        await _agent_conn_pool.close()
        logger.info("agent_connection_pool_closed")
    logger.info("application_shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Set up Prometheus metrics
setup_metrics(app)

# Add logging context middleware (must be added before other middleware to capture context)
app.add_middleware(LoggingContextMiddleware)

# Add custom metrics middleware
app.add_middleware(MetricsMiddleware)

# Add profiling middleware (DEBUG only — saves HTML to /tmp on slow requests)
if settings.DEBUG:
    app.add_middleware(ProfilingMiddleware)

# Add correlation ID middleware — must be outermost so request_id is set before all others
app.add_middleware(CorrelationIdMiddleware)

# Set up rate limiter exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # pyright: ignore[reportArgumentType]


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    logger.error(
        "validation_error",
        client_host=request.client.host if request.client else "unknown",
        path=request.url.path,
        errors=str(exc.errors()),
    )

    formatted_errors = []
    for error in exc.errors():
        loc = " -> ".join([str(loc_part) for loc_part in error["loc"] if loc_part != "body"])
        formatted_errors.append({"field": loc, "message": error["msg"]})

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": formatted_errors},
    )


# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["root"][0])
async def root(request: Request):
    """Root endpoint returning basic API information."""
    logger.info("root_endpoint_called")
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "healthy",
        "environment": settings.ENVIRONMENT.value,
        "swagger_url": "/docs",
        "redoc_url": "/redoc",
    }


@app.get("/health")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["health"][0])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint — returns 503 if the database is unreachable."""
    logger.info("health_check_called")

    db_healthy = await database_service.health_check()

    response = {
        "status": "healthy" if db_healthy else "degraded",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT.value,
        "components": {"api": "healthy", "database": "healthy" if db_healthy else "unhealthy"},
        "timestamp": datetime.now().isoformat(),
    }

    status_code = status.HTTP_200_OK if db_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=response, status_code=status_code)
