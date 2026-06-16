"""Lazily-initialised singletons for shared services + pipeline agents.

All singletons are construction-only — none hit the network or the database
at import time.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.agent_config import agent_settings
from app.services.openai_client import OpenAIService
from app.services.salesforce_client import SalesforceClient
from app.services.vector_store import VectorStoreService
from app.agents.workers.mapper_worker.tools import MapperAgent
from app.services.connector_schema import (
    ConnectorSchemaService,
    DestinationRegistryService,
    InternalRegistryService,
    SourceRegistryService,
)

settings = agent_settings

# --- External-service clients ---
openai = OpenAIService(agent_settings)
vector_store = VectorStoreService(agent_settings)
salesforce = SalesforceClient(agent_settings)  # env-var fallback (dev / test)


def salesforce_for_project(project_id) -> SalesforceClient:
    """Return a SalesforceClient scoped to a specific project.

    Loads OAuth tokens from ProjectConnectionSecret for the given project_id.
    """
    from uuid import UUID

    pid = UUID(str(project_id)) if project_id and not isinstance(project_id, UUID) else project_id
    return SalesforceClient(agent_settings, project_id=pid)


# --- Shared async DB engine + session maker ---
db_engine = create_async_engine(agent_settings.database_url, echo=False, future=True)
session_maker = async_sessionmaker(db_engine, expire_on_commit=False)

# --- Schema registry services ---
connector_schema = ConnectorSchemaService(agent_settings, session_maker)
destination_registry = DestinationRegistryService(agent_settings, session_maker)
internal_registry = InternalRegistryService(agent_settings, session_maker)
source_registry = SourceRegistryService(agent_settings, session_maker)

# --- Mapper pipeline agent ---
mapper = MapperAgent(agent_settings, openai, vector_store)
