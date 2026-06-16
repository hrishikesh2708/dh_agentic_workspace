"""Lazily-initialised singletons for shared services + pipeline agents.

Stage 1 wave 3 lands only the foundational services (OpenAI, Salesforce,
vector store, connector schema registry) plus the SQLAlchemy session maker. The
remaining pipeline-agent singletons (mapper, validator, scorer,
schema_extractor, internal_schema, schema_registry) are appended as each
worker module is ported in Wave 4.

All singletons here are construction-only — none of them hit the network
or the database at import time.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from app.agents.core.agent_config import agent_settings
from app.agents.shared_tools.openai_client import OpenAIService
from app.services.connector_schema import (
    ConnectorSchemaService,
    DestinationRegistryService,
    InternalRegistryService,
    SourceRegistryService,
)
from app.agents.shared_tools.salesforce_client import SalesforceClient
from app.agents.shared_tools.vector_store import VectorStoreService
from app.agents.workers.mapper_worker.tools import MapperAgent
from app.agents.workers.reviewer_worker.tools import (
    ConfidenceScorerAgent,
    ValidatorAgent,
)
from app.agents.workers.schema_worker.tools import (
    InternalSchemaAgent,
    SchemaExtractorAgent,
    SchemaRegistryAgent,
)

settings = agent_settings

# --- External-service clients (foundational) ---
openai = OpenAIService(agent_settings)
vector_store = VectorStoreService(agent_settings)
salesforce = SalesforceClient(agent_settings)  # env-var fallback (dev / test)


def salesforce_for_project(project_id) -> SalesforceClient:
    """Return a SalesforceClient scoped to a specific project.

    Loads OAuth tokens from ProjectConnectionSecret for the given project_id.
    Falls back to env-var credentials when project_id is None.
    """
    from uuid import UUID

    pid = UUID(str(project_id)) if project_id and not isinstance(project_id, UUID) else project_id
    return SalesforceClient(agent_settings, project_id=pid)


# --- Shared async DB engine (used by reviewer_worker + connector catalog) ---
db_engine = create_async_engine(agent_settings.database_url, echo=False, future=True)
session_maker = async_sessionmaker(db_engine, expire_on_commit=False)

# --- Schema registry services (used by schema_worker + reviewer_worker) ---
connector_schema = ConnectorSchemaService(agent_settings, session_maker)
destination_registry = DestinationRegistryService(agent_settings, session_maker)
internal_registry = InternalRegistryService(agent_settings, session_maker)
source_registry = SourceRegistryService(agent_settings, session_maker)

# --- Schema-stage pipeline agents (Wave 4: schema_worker) ---
schema_extractor = SchemaExtractorAgent(salesforce)
internal_schema = InternalSchemaAgent(agent_settings)
schema_registry = SchemaRegistryAgent(agent_settings)

# --- Mapper pipeline agent (Wave 4: mapper_worker) ---
mapper = MapperAgent(agent_settings, openai, vector_store)

# --- Reviewer-stage pipeline agents (Wave 4: reviewer_worker) ---
validator = ValidatorAgent()
scorer = ConfidenceScorerAgent(agent_settings)
