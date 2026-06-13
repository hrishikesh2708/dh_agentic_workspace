"""Domain types for the mapping agent (ported from crawler_agent ``src/domain/types.py``)."""

from app.schemas.agent.types import (
    CanonicalSchema,
    CanonicalSchemaField,
    DestinationField,
    DestinationSchema,
    MappingKind,
    MappingStatus,
    ProposedMapping,
    SourceField,
    SourceSchema,
    Sources,
    ValidationStatus,
)

__all__ = [
    "CanonicalSchema",
    "CanonicalSchemaField",
    "DestinationField",
    "DestinationSchema",
    "MappingKind",
    "MappingStatus",
    "ProposedMapping",
    "SourceField",
    "SourceSchema",
    "Sources",
    "ValidationStatus",
]
