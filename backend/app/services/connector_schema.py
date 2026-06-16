"""Unified connector schema service (sources, destinations, canonical).

Consolidates YAML-backed schema registries and UI catalog helpers that were
previously split across ``CatalogService``, ``DestinationRegistryService``, and
``InternalRegistryService`` in ``app.services.registries``.

Planned / expected functionality
--------------------------------
* **Source schemas** — enumerate source connector types (Salesforce, HubSpot, …),
  load source-side schema definitions from YAML, and expose UI picker options
  (replacing hardcoded ``SOURCE_OPTIONS`` in ``constants.py``).
* **Destination schemas** — list projection targets, load destination YAML
  schemas, and return enabled picker options for the intent flow.
* **Canonical schema** — load the single internal/canonical schema file and
  expose it as a catalog option when mapping to the canonical model.
* **Catalog helpers** — async wrappers for picker UIs: list options, resolve
  labels, and validate enabled destination IDs.
* **Validation hooks** — shared helpers to check that a user-selected source /
  destination / canonical ID exists and is enabled before pipeline stages run.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import String, cast
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload
from sqlmodel import col, select

from app.agents.core.agent_config import (
    _AgentSettingsProxy,
)
from app.models import Connector, ConnectorStatus, ConnectorType
from app.models import DestinationFieldMapping
from app.schemas import (
    DestinationField,
    DestinationSchema,
    Sources,
    Destinations,
    CanonicalSchemaField,
    CanonicalSchema,
)
from app.models import CanonicalField
from app.agents.core.intent_validation import destination_platform_id


def _connector_stmt(*where_clauses):
    """Base connector query with parent relationship eagerly loaded."""
    return select(Connector).options(selectinload(Connector.parent)).where(*where_clauses)  # type: ignore[arg-type]


def _catalog_option_from_connector(connector: Connector) -> dict[str, Any]:
    """Normalise a connector row into the catalog/picker option shape."""
    platform_id = destination_platform_id(connector.sub_connector_of, connector.connector_slug)
    label = connector.parent.display_name if connector.parent else connector.display_name
    return {
        "id": platform_id,
        "label": label,
        "description": "",
        "enabled": connector.status == ConnectorStatus.active,
    }


def _dedupe_destination_options(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse sub-connector rows to one option per platform slug."""
    by_platform: dict[str, dict[str, Any]] = {}
    for option in options:
        platform_id = str(option["id"]).lower()
        existing = by_platform.get(platform_id)
        if existing is None:
            by_platform[platform_id] = dict(option)
            continue
        existing["enabled"] = bool(existing.get("enabled")) or bool(option.get("enabled"))
    return list(by_platform.values())


class DestinationRegistryService:
    """Loads destination schemas (Meta, Google) from db."""

    def __init__(self, settings: _AgentSettingsProxy, session_maker: async_sessionmaker) -> None:
        """Initialise with agent settings and an async session factory."""
        self.settings = settings
        self._session_maker = session_maker

    async def list_destinations(self) -> list[Destinations]:
        """Return active/disabled destination connectors from the database."""
        stmt = _connector_stmt(
            cast(col(Connector.connector_type), String) == ConnectorType.destination.value,
            cast(col(Connector.status), String).in_([ConnectorStatus.active.value, ConnectorStatus.disabled.value]),
        ).order_by(col(Connector.display_name))
        async with self._session_maker() as db:
            result = await db.execute(stmt)
            connectors = list(result.scalars().all())
            return [
                Destinations(
                    connector_id=c.connector_slug,
                    connector_type=c.connector_type.value,
                    display_name=c.display_name,
                    sub_connector_of=c.sub_connector_of,
                    parent_connector_id=c.parent.connector_slug if c.parent else None,
                    parent_connector_name=c.parent.display_name if c.parent else None,
                )
                for c in connectors
            ]

    async def list_destination_feild(self, destination_slug: str) -> list[DestinationFieldMapping]:
        """Load destination field mappings for a connector slug."""
        stmt = (
            select(DestinationFieldMapping)
            .where(col(DestinationFieldMapping.destination_slug) == destination_slug)
            .order_by(col(DestinationFieldMapping.is_required), col(DestinationFieldMapping.destination_field_path))
        )
        async with self._session_maker() as db:
            result = await db.execute(stmt)
            destination_fields = list[DestinationFieldMapping](result.scalars().all())
        if not destination_fields:
            raise ValueError(f"Destination fields not found: {destination_slug}")
        return destination_fields

    async def load_destination_schema(self, Connector: Connector) -> DestinationSchema:
        """Build a :class:`DestinationSchema` from connector field-mapping rows."""
        destination_fields = await self.list_destination_feild(
            str(Connector.parent.connector_slug) if Connector.parent else str(Connector.connector_slug)
        )
        formatted_destination_fields = [
            DestinationField(
                name=df.destination_field_path,
                type="string",
                canonical_key=df.canonical_key,
                required=df.is_required,
                transform_function=df.transform_function,
                description=None,  # df.description,
                enum_values=[],  # df.enum_values,
                constraints={},  # df.constraints,
            )
            for df in destination_fields
        ]
        return DestinationSchema(
            destination=str(Connector.connector_slug),
            label=Connector.parent.display_name if Connector.parent else Connector.display_name,
            status=Connector.status.value,
            fields=formatted_destination_fields,
        )


class InternalRegistryService:
    """Loads the internal canonical schema (one file, by name)."""

    def __init__(self, settings: _AgentSettingsProxy, session_maker: async_sessionmaker) -> None:
        """Initialise with an agent settings proxy and async session factory.

        Args:
            settings: Provides ``destination_schema_dir`` / ``internal_schema_dir``.
            session_maker: Async SQLAlchemy session factory for canonical queries.
        """
        self.settings = settings
        self._session_maker = session_maker

    async def load_canonical_schema(self) -> CanonicalSchema:
        """Load canonical schema fields from the ``canonical_field`` table."""
        stmt = select(CanonicalField).order_by(col(CanonicalField.canonical_key))
        async with self._session_maker() as db:
            result = await db.execute(stmt)
            canonical_fields = [
                CanonicalSchemaField(
                    canonical_key=row.canonical_key,
                    field_label=row.field_label,
                    field_hint=row.field_hint,
                    field_category=row.field_category.value,
                    is_pii=row.is_pii,
                )
                for row in result.scalars().all()
            ]
        return CanonicalSchema(
            canonical="canonical",
            label="Datahash Canonical",
            description="Internal canonical schema",
            fields=canonical_fields,
        )


class CatalogService:
    """UI catalog of destination options for picker UIs."""

    def __init__(
        self,
        settings: _AgentSettingsProxy,
        session_maker: async_sessionmaker,
    ) -> None:
        """Initialise the destination catalog.

        Args:
            settings: Agent settings proxy (unused today; kept for symmetry).
            session_maker: Async SQLAlchemy session factory for connector queries.
        """
        self._session_maker = session_maker

    async def list_destination_options(self) -> list[dict]:
        """Return UI-ready destination options from the connector table.

        Includes rows with ``active`` or ``disabled`` status; ``inactive`` rows
        are omitted. ``enabled`` is ``True`` only for ``active`` connectors.
        """
        # Columns are stored as plain text in Postgres; cast avoids native enum binding.
        stmt = _connector_stmt(
            cast(col(Connector.connector_type), String) == ConnectorType.destination.value,
            cast(col(Connector.status), String).in_([ConnectorStatus.active.value, ConnectorStatus.disabled.value]),
        ).order_by(col(Connector.display_name))
        async with self._session_maker() as db:
            result = await db.execute(stmt)
            connectors = list(result.scalars().all())
            return _dedupe_destination_options([_catalog_option_from_connector(c) for c in connectors])

    async def destination_label(self, dest_id: str) -> str:
        """Resolve a destination ID to its human-readable label."""
        options = await self.list_destination_options()
        return self._label_from_options(dest_id, options)

    async def enabled_destination_ids(self) -> set[str]:
        """Set of selectable (active) destination platform IDs (lowercased).

        Uses ``sub_connector_of`` when set, otherwise ``connector_slug``.
        """
        stmt = _connector_stmt(
            cast(col(Connector.connector_type), String) == ConnectorType.destination.value,
            cast(col(Connector.status), String) == ConnectorStatus.active.value,
        )
        async with self._session_maker() as db:
            result = await db.execute(stmt)
            connectors = list(result.scalars().all())
        return {destination_platform_id(c.sub_connector_of, c.connector_slug).lower() for c in connectors}

    @staticmethod
    def _label_from_options(dest_id: str, options: list[dict]) -> str:
        needle = dest_id.lower().strip()
        for option in options:
            if option["id"].lower() == needle:
                return option["label"]
        return dest_id.replace("_", " ").title()


class SourceRegistryService:
    """Loads source schemas (Salesforce, HubSpot, etc.) from db."""

    def __init__(self, settings: _AgentSettingsProxy, session_maker: async_sessionmaker) -> None:
        """Initialise with agent settings and an async session factory."""
        self.settings = settings
        self._session_maker = session_maker

    async def list_source(self) -> list[Sources]:
        """Return active source connectors from the database."""
        stmt = _connector_stmt(
            cast(col(Connector.connector_type), String) == ConnectorType.source.value,
            cast(col(Connector.status), String) == ConnectorStatus.active.value,
        ).order_by(col(Connector.display_name))
        async with self._session_maker() as db:
            result = await db.execute(stmt)
            connectors = list(result.scalars().all())
            return [
                Sources(
                    connector_id=c.connector_slug,
                    connector_type=c.connector_type.value,
                    display_name=c.display_name,
                    sub_connector_of=c.sub_connector_of,
                    parent_connector_id=c.parent.connector_slug if c.parent else None,
                    parent_connector_name=c.parent.display_name if c.parent else None,
                )
                for c in connectors
            ]


class ConnectorSchemaService:
    """Single entry point for source, destination, and canonical schema access."""

    def __init__(
        self,
        settings: _AgentSettingsProxy,
        session_maker: async_sessionmaker,
    ) -> None:
        """Wire destination, canonical, catalog, and source registry services."""
        self._settings = settings
        self._destinations = DestinationRegistryService(settings, session_maker)
        self._canonical = InternalRegistryService(settings, session_maker)
        self._catalog = CatalogService(settings, session_maker)
        self._sources = SourceRegistryService(settings, session_maker)

    # --- Destination schemas (projection targets) ---

    async def list_destination_types(self) -> list[str]:
        """Enumerate available destination connector slugs."""
        destinations = await self._destinations.list_destinations()
        return [d.connector_id for d in destinations]

    def load_destination_schema(self, destination_type: str) -> DestinationSchema:
        """Load a destination schema by connector slug (not yet wired)."""
        raise NotImplementedError(
            "Destination schema loading by slug is not implemented; "
            "use DestinationRegistryService.load_destination_schema."
        )

    def list_destination_options_sync(self) -> list[dict]:
        """Return UI-ready destination catalog options (sync)."""
        return asyncio.run(self.list_destination_options())

    # --- Canonical / internal schema ---

    async def load_canonical_schema(self) -> CanonicalSchema:
        """Load the internal canonical schema from the database."""
        return await self._canonical.load_canonical_schema()

    async def list_canonical_option(self) -> dict:
        """Return the canonical schema as a catalog option."""
        return {
            "id": "canonical",
            "label": "Datahash Canonical",
            "description": "Internal canonical schema",
            "enabled": True,
        }

    # --- Catalog helpers (async, for intent / message layers) ---

    async def list_destination_options(self) -> list[dict]:
        """Async wrapper over blocking destination YAML loads."""
        return await self._catalog.list_destination_options()

    async def destination_label(self, dest_id: str) -> str:
        """Resolve a destination ID to its human-readable label."""
        return await self._catalog.destination_label(dest_id)

    async def enabled_destination_ids(self) -> set[str]:
        """Set of all enabled destination IDs (lowercased)."""
        return await self._catalog.enabled_destination_ids()

    # --- Source schemas (stub — wire SourceRegistryService when YAML lands) ---

    async def list_source_types(self) -> list[str]:
        """Enumerate available source connector slugs."""
        sources = await self._sources.list_source()
        return [s.connector_id for s in sources]

    def load_source_schema(self, source_type: str) -> DestinationSchema:
        """Placeholder until source schema loading is wired to the database."""
        raise NotImplementedError("Source schema registry not implemented yet.")

    async def enabled_source_ids(self) -> set[str]:
        """Set of all active source connector slugs (lowercased)."""
        sources = await self._sources.list_source()
        return {s.connector_id.lower() for s in sources}

    async def source_label(self, source_id: str) -> str:
        """Resolve a source slug to its human-readable label."""
        sources = await self._sources.list_source()
        needle = source_id.lower().strip()
        for source in sources:
            if source.connector_id.lower() == needle:
                return source.display_name
        return source_id.replace("_", " ").title()

    async def list_picker_source_options(self) -> list[dict]:
        """Return UI-ready source catalog options from the connector table."""
        sources = await self._sources.list_source()
        return [
            {
                "id": s.connector_id,
                "label": s.display_name,
                "description": "",
                "enabled": True,
            }
            for s in sources
        ]
