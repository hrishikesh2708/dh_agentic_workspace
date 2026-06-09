"""schema_worker pipeline agents.

Ported from three crawler_agent files:

- ``src/pipeline/schema_extractor.py``  → :class:`SchemaExtractorAgent`
- ``src/pipeline/internal_schema.py``   → :class:`InternalSchemaAgent`
- ``src/pipeline/schema_registry.py``   → :class:`SchemaRegistryAgent`
   (used in projection mode to load destination-specific schemas)
"""

from __future__ import annotations

from app.agents.core.agent_config import _AgentSettingsProxy
from app.agents.shared_tools.registries import (
    DestinationRegistryService,
    InternalRegistryService,
)
from app.agents.shared_tools.salesforce_client import SourceClient
from app.schemas.agent.types import DestinationSchema


class _PipelineStateLike:
    """Minimal duck-type interface the pipeline agents mutate.

    They only touch ``source_schema`` / ``destination_schema`` /
    ``destination_type`` / ``source_object`` / ``vector_search_destination_type``
    — both :class:`GlobalAgentState` and the legacy ``MappingGraphState`` satisfy
    this contract.
    """


class SchemaExtractorAgent:
    """Fetch the source schema for the current ``source_object`` via Salesforce."""

    def __init__(self, source_client: SourceClient) -> None:
        """Inject the configured source client (Salesforce by default).

        Args:
            source_client: Any :class:`SourceClient` implementation.
        """
        self.source_client = source_client

    async def run(self, state):
        """Mutate ``state.source_schema`` in place and return ``state``."""
        source_schema = await self.source_client.load_source_schema(state.source_object)
        state.source_schema = source_schema
        return state


class InternalSchemaAgent:
    """Load the internal canonical schema (used in canonical-stage mapping)."""

    def __init__(self, settings: _AgentSettingsProxy) -> None:
        """Initialise an internal registry service.

        Args:
            settings: Agent settings proxy (used by the registry to find YAML).
        """
        self.registry = InternalRegistryService(settings)

    async def run(self, state):
        """Set ``destination_schema`` + ``destination_type`` to the canonical schema."""
        schema = self.registry.load_schema()
        state.destination_schema = schema
        state.destination_type = "canonical"
        state.vector_search_destination_type = "canonical"
        return state


class SchemaRegistryAgent:
    """Load a destination-specific schema (used in projection-stage mapping)."""

    def __init__(self, settings: _AgentSettingsProxy) -> None:
        """Initialise a destination registry service.

        Args:
            settings: Agent settings proxy.
        """
        self.registry = DestinationRegistryService(settings)

    async def run(self, state):
        """Set ``destination_schema`` to the projection target's schema."""
        state.destination_schema = self.registry.load_schema(state.destination_type)
        return state

    def load_schema(self, destination_type: str) -> DestinationSchema:
        """Synchronous schema loader (used by registries, not by graph nodes)."""
        return self.registry.load_schema(destination_type)
