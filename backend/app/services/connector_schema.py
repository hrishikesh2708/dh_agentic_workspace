"""Unified connector schema service (sources, destinations, canonical).

All registry queries now hit the ``source`` and ``destination`` tables directly.
The ``connector`` table has been removed.
"""

# ruff: noqa: D102, D107

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import col, select

from app.agents.agent_config import _AgentSettingsProxy
from app.models import DatahashSchema
from app.models import Destination, DestinationSchemaMapping, DestinationStatus
from app.models import Source
from app.schemas import (
    CanonicalSchema,
    CanonicalSchemaField,
    DestinationField,
    DestinationSchema,
    Destinations,
    Sources,
)


class DestinationRegistryService:
    """Loads destination records from the ``destination`` table."""

    def __init__(self, settings: _AgentSettingsProxy, session_maker: async_sessionmaker) -> None:
        self.settings = settings
        self._session_maker = session_maker

    async def list_destinations(self) -> list[Destinations]:
        """Return all non-deleted destinations."""
        stmt = (
            select(Destination).where(col(Destination.is_deleted).is_(False)).order_by(col(Destination.display_name))
        )
        async with self._session_maker() as db:
            result = await db.execute(stmt)
            destinations = list(result.scalars().all())
        return [
            Destinations(
                connector_id=d.name,
                connector_type="destination",
                display_name=d.display_name,
            )
            for d in destinations
        ]

    async def list_destination_schema_mappings(self, destination_name: str) -> list[DestinationSchemaMapping]:
        """Load DestinationSchemaMapping rows for a destination name."""
        async with self._session_maker() as db:
            dest_result = await db.execute(
                select(Destination).where(
                    Destination.name == destination_name,
                    col(Destination.is_deleted).is_(False),
                )
            )
            dest = dest_result.scalars().first()
            if not dest:
                raise ValueError(f"Destination not found: {destination_name}")
            result = await db.execute(
                select(DestinationSchemaMapping)
                .where(
                    col(DestinationSchemaMapping.destination_id) == dest.id,
                    col(DestinationSchemaMapping.is_deleted).is_(False),
                )
                .order_by(
                    col(DestinationSchemaMapping.is_required).desc(),
                    col(DestinationSchemaMapping.field_name),
                )
            )
            return list(result.scalars().all())

    async def load_destination_schema(self, destination_name: str) -> DestinationSchema:
        """Build a DestinationSchema from DestinationSchemaMapping rows."""
        async with self._session_maker() as db:
            dest_result = await db.execute(
                select(Destination).where(
                    Destination.name == destination_name,
                    col(Destination.is_deleted).is_(False),
                )
            )
            dest = dest_result.scalars().first()
        if not dest:
            raise ValueError(f"Destination not found: {destination_name}")

        mappings = await self.list_destination_schema_mappings(destination_name)
        formatted = [
            DestinationField(
                name=m.field_name,
                type="string",
                canonical_key=str(m.datahash_schema_id),
                required=m.is_required,
                transform_function=m.transform_function,
                description=None,
                enum_values=[],
                constraints={},
            )
            for m in mappings
        ]
        return DestinationSchema(
            destination=dest.name,
            label=dest.display_name,
            status=dest.status.value,
            fields=formatted,
        )


class InternalRegistryService:
    """Loads the internal canonical schema from ``datahash_schema``."""

    def __init__(self, settings: _AgentSettingsProxy, session_maker: async_sessionmaker) -> None:
        self.settings = settings
        self._session_maker = session_maker

    async def load_canonical_schema(self) -> CanonicalSchema:
        stmt = (
            select(DatahashSchema)
            .where(col(DatahashSchema.is_deleted).is_(False))
            .order_by(col(DatahashSchema.canonical_key))
        )
        async with self._session_maker() as db:
            result = await db.execute(stmt)
            canonical_fields = [
                CanonicalSchemaField(
                    canonical_key=row.canonical_key,
                    field_label=row.label,
                    field_hint=row.hint,
                    field_category=row.category.value,
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

    def __init__(self, settings: _AgentSettingsProxy, session_maker: async_sessionmaker) -> None:
        self._session_maker = session_maker

    async def list_destination_options(self) -> list[dict]:
        """Return UI-ready destination options from the destination table.

        ``enabled`` is True only for active destinations.
        """
        stmt = (
            select(Destination).where(col(Destination.is_deleted).is_(False)).order_by(col(Destination.display_name))
        )
        async with self._session_maker() as db:
            result = await db.execute(stmt)
            destinations = list(result.scalars().all())
        return [
            {
                "id": d.name,
                "label": d.display_name,
                "description": "",
                "enabled": d.status == DestinationStatus.active,
            }
            for d in destinations
        ]

    async def destination_label(self, dest_id: str) -> str:
        """Resolve a destination name to its human-readable label."""
        options = await self.list_destination_options()
        needle = dest_id.lower().strip()
        for option in options:
            if option["id"].lower() == needle:
                return option["label"]
        return dest_id.replace("_", " ").title()

    async def enabled_destination_ids(self) -> set[str]:
        """Set of active destination names (lowercased)."""
        stmt = select(Destination).where(
            col(Destination.is_deleted).is_(False),
            Destination.status == DestinationStatus.active,
        )
        async with self._session_maker() as db:
            result = await db.execute(stmt)
            destinations = list(result.scalars().all())
        return {d.name.lower() for d in destinations}


class SourceRegistryService:
    """Loads source records from the ``source`` table."""

    def __init__(self, settings: _AgentSettingsProxy, session_maker: async_sessionmaker) -> None:
        self.settings = settings
        self._session_maker = session_maker

    async def list_source(self) -> list[Sources]:
        """Return active sources from the database."""
        stmt = (
            select(Source)
            .where(col(Source.is_active).is_(True), col(Source.is_deleted).is_(False))
            .order_by(col(Source.display_name))
        )
        async with self._session_maker() as db:
            result = await db.execute(stmt)
            sources = list(result.scalars().all())
        return [
            Sources(
                connector_id=s.name,
                connector_type="source",
                display_name=s.display_name,
            )
            for s in sources
        ]


class ConnectorSchemaService:
    """Single entry point for source, destination, and canonical schema access."""

    def __init__(self, settings: _AgentSettingsProxy, session_maker: async_sessionmaker) -> None:
        self._settings = settings
        self._destinations = DestinationRegistryService(settings, session_maker)
        self._canonical = InternalRegistryService(settings, session_maker)
        self._catalog = CatalogService(settings, session_maker)
        self._sources = SourceRegistryService(settings, session_maker)

    async def list_destination_types(self) -> list[str]:
        destinations = await self._destinations.list_destinations()
        return [d.connector_id for d in destinations]

    def load_destination_schema(self, destination_type: str) -> DestinationSchema:
        raise NotImplementedError("Use DestinationRegistryService.load_destination_schema.")

    def list_destination_options_sync(self) -> list[dict]:
        return asyncio.run(self.list_destination_options())

    async def load_canonical_schema(self) -> CanonicalSchema:
        return await self._canonical.load_canonical_schema()

    async def list_canonical_option(self) -> dict:
        return {
            "id": "canonical",
            "label": "Datahash Canonical",
            "description": "Internal canonical schema",
            "enabled": True,
        }

    async def list_destination_options(self) -> list[dict]:
        return await self._catalog.list_destination_options()

    async def destination_label(self, dest_id: str) -> str:
        return await self._catalog.destination_label(dest_id)

    async def enabled_destination_ids(self) -> set[str]:
        return await self._catalog.enabled_destination_ids()

    async def list_source_types(self) -> list[str]:
        sources = await self._sources.list_source()
        return [s.connector_id for s in sources]

    def load_source_schema(self, source_type: str) -> DestinationSchema:
        raise NotImplementedError("Source schema registry not implemented yet.")

    async def enabled_source_ids(self) -> set[str]:
        sources = await self._sources.list_source()
        return {s.connector_id.lower() for s in sources}

    async def source_label(self, source_id: str) -> str:
        sources = await self._sources.list_source()
        needle = source_id.lower().strip()
        for source in sources:
            if source.connector_id.lower() == needle:
                return source.display_name
        return source_id.replace("_", " ").title()

    async def list_picker_source_options(self) -> list[dict]:
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
