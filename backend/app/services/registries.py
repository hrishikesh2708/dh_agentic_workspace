"""Schema registry loaders + destination/canonical catalog.

Consolidates four files from crawler_agent's ``src/integrations/registries/``
(catalog, destination_registry, internal_registry) and
``src/pipeline/schema_registry.py``. Single module so callers don't have to
juggle multiple imports for closely-related YAML loaders.
"""

from __future__ import annotations

import asyncio
from typing import Any

import yaml

from app.agents.agent_config import (
    _AgentSettingsProxy,
    resolve_agent_path,
)
from app.schemas import DestinationSchema


def _catalog_option_from_raw(raw: dict[str, Any], *, fallback_id: str) -> dict[str, Any]:
    """Normalise a raw YAML schema into the catalog/picker option shape."""
    dest_id = str(raw.get("destination_type") or fallback_id)
    label = raw.get("label") or dest_id.replace("_", " ").title()
    description = raw.get("description") or ""
    enabled = raw.get("enabled", True)
    if isinstance(enabled, str):
        enabled = enabled.lower() not in ("false", "0", "no")
    return {
        "id": dest_id,
        "label": str(label),
        "description": str(description),
        "enabled": bool(enabled),
    }


class DestinationRegistryService:
    """Loads destination schemas (Meta CAPI, Google DM, etc.) from YAML."""

    def __init__(self, settings: _AgentSettingsProxy) -> None:
        """Initialise with an agent settings proxy.

        Args:
            settings: Provides ``destination_schema_dir`` / ``internal_schema_dir``.
        """
        self.settings = settings

    def _schema_dir(self):
        return resolve_agent_path(self.settings.destination_schema_dir)

    def list_destination_types(self) -> list[str]:
        """Enumerate available destination schema IDs (filenames sans ``.yaml``)."""
        schema_dir = self._schema_dir()
        if not schema_dir.exists():
            return []
        return sorted(p.stem for p in schema_dir.glob("*.yaml") if not p.stem.startswith("_"))

    def _load_raw(self, destination_type: str) -> dict:
        schema_path = self._schema_dir() / f"{destination_type}.yaml"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        raw = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid schema file: {schema_path}")
        return raw

    def load_schema(self, destination_type: str) -> DestinationSchema:
        """Load + validate a destination schema by ID."""
        return DestinationSchema.model_validate(self._load_raw(destination_type))

    def list_destination_options(self) -> list[dict]:
        """Return UI-ready catalog options (id/label/description/enabled)."""
        options: list[dict] = []
        for schema_id in self.list_destination_types():
            raw = self._load_raw(schema_id)
            option = _catalog_option_from_raw(raw, fallback_id=schema_id)
            if option["enabled"]:
                options.append(option)
        return options


class InternalRegistryService:
    """Loads the internal canonical schema (one file, by name)."""

    def __init__(self, settings: _AgentSettingsProxy) -> None:
        """Initialise with an agent settings proxy.

        Args:
            settings: Provides ``destination_schema_dir`` / ``internal_schema_dir``.
        """
        self.settings = settings

    def _schema_path(self):
        name = self.settings.internal_schema_name
        return resolve_agent_path(self.settings.internal_schema_dir) / f"{name}.yaml"

    def _load_raw(self) -> dict:
        schema_path = self._schema_path()
        if not schema_path.exists():
            raise FileNotFoundError(f"Internal schema file not found: {schema_path}")
        raw = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid schema file: {schema_path}")
        return raw

    def load_schema(self) -> DestinationSchema:
        """Load + validate the canonical schema."""
        return DestinationSchema.model_validate(self._load_raw())

    def list_canonical_option(self) -> dict:
        """Return the canonical schema as a catalog option (for the destination picker)."""
        raw = self._load_raw()
        return _catalog_option_from_raw(raw, fallback_id="canonical")


class CatalogService:
    """UI catalog of destination options for picker UIs."""

    def __init__(self, settings: _AgentSettingsProxy) -> None:
        """Initialise the destination registry.

        Args:
            settings: Agent settings proxy shared with the destination registry.
        """
        self._destinations = DestinationRegistryService(settings)

    def _list_destination_options_blocking(self) -> list[dict]:
        return self._destinations.list_destination_options()

    async def list_destination_options(self) -> list[dict]:
        """Async wrapper over the blocking YAML load."""
        return await asyncio.to_thread(self._list_destination_options_blocking)

    async def destination_label(self, dest_id: str) -> str:
        """Resolve a destination ID to its human-readable label."""
        options = await self.list_destination_options()
        return self._label_from_options(dest_id, options)

    async def enabled_destination_ids(self) -> set[str]:
        """Set of all enabled destination IDs (lowercased)."""
        options = await self.list_destination_options()
        return {o["id"].lower() for o in options}

    @staticmethod
    def _label_from_options(dest_id: str, options: list[dict]) -> str:
        needle = dest_id.lower().strip()
        for option in options:
            if option["id"].lower() == needle:
                return option["label"]
        return dest_id.replace("_", " ").title()
