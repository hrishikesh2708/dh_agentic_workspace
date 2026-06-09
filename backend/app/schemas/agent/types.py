"""Domain Pydantic models for the mapping agent.

Ported verbatim from ``crawler_agent/frontend/agent/src/domain/types.py`` —
this is the contract between workers, the supervisor, and persistence.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


class MappingStatus(str, Enum):
    """Lifecycle of a single proposed mapping."""

    auto_approved = "auto_approved"
    needs_review = "needs_review"
    unmatched = "unmatched"
    not_proposed = "not_proposed"
    human_approved = "human_approved"
    human_corrected = "human_corrected"


class Sources(str, Enum):
    """Source CRMs we can ingest from."""

    salesforce = "salesforce"
    hubspot = "hubspot"
    postgres = "postgres"
    snowflake = "snowflake"


class ValidationStatus(str, Enum):
    """Outcome of mapping validation (type compatibility, required fields, etc.)."""

    pass_status = "pass"
    warn = "warn"
    fail = "fail"


class SourceField(BaseModel):
    """A single field on the source schema (e.g. a Salesforce column)."""

    name: str
    label: str
    type: str
    description: str | None = None
    picklist_values: list[str] = Field(default_factory=list)
    sample_values: list[str] = Field(default_factory=list)
    is_custom: bool = False


class SourceSchema(BaseModel):
    """The full source schema for one object (e.g. Salesforce Lead)."""

    object_name: str
    fields: list[SourceField]


class DestinationField(BaseModel):
    """A single field on the destination schema (canonical or projection)."""

    name: str
    type: str
    required: bool = False
    description: str | None = None
    enum_values: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)


class DestinationSchema(BaseModel):
    """The full destination schema (canonical, meta_capi, google_dm, ...)."""

    destination_type: str
    version: str = "1.0"
    label: str | None = None
    description: str | None = None
    enabled: bool = True
    fields: list[DestinationField]


class ProposedMapping(BaseModel):
    """One mapping proposal: source field → destination field, with confidence + status."""

    source_field: str
    destination_field: str | None = None
    confidence: float = 0.0
    reasoning: str = ""
    transformation_needed: str | None = None
    validation_status: ValidationStatus = ValidationStatus.pass_status
    validation_notes: list[str] = Field(default_factory=list)
    status: MappingStatus = MappingStatus.needs_review

    @field_validator("transformation_needed", mode="before")
    @classmethod
    def _coerce_transformation_needed(cls, value: Any) -> Any:
        """Older payloads sent a bool here — coerce to the string convention."""
        if isinstance(value, bool):
            return "required" if value else None
        return value


class MappingKind(str, Enum):
    """Pipeline stage indicator: canonical (source→internal) or projection (internal→destination)."""

    canonical = "canonical"
    projection = "projection"
