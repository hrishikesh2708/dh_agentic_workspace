"""Domain types for the mapping agent (ported from crawler_agent ``src/domain/types.py``)."""

from app.schemas.agent.types import (
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
