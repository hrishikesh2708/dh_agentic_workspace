"""Pydantic schemas for mapping-session dashboard endpoints."""

from datetime import datetime
from typing import (
    List,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)

from app.schemas.base import BaseResponse


class FieldMappingRead(BaseModel):
    """A single source -> destination proposal inside a session.

    Attributes:
        id: Primary key.
        session_id: FK to ``mapping_session.id``.
        source_field: The source-side field name.
        destination_field: The destination-side field name (nullable for
            unmatched proposals).
        confidence: 0.0-1.0 LLM/penalty-adjusted score.
        status: Lifecycle status (e.g. ``auto_approved``, ``needs_review``).
        reasoning: LLM-provided rationale.
        transformation: Optional transformation hint.
        validation_status: ``pass`` / ``warn`` / ``fail``.
        validation_notes: List of validation messages.
        created_at: When this row was created.
    """

    id: int = Field(..., description="Field-mapping primary key")
    session_id: int = Field(..., description="Owning mapping session id")
    source_field: str = Field(..., description="Source-side field name")
    destination_field: Optional[str] = Field(default=None, description="Destination-side field name")
    confidence: float = Field(..., description="Confidence score (0.0-1.0)")
    status: str = Field(..., description="Lifecycle status")
    reasoning: str = Field(default="", description="LLM rationale for the mapping")
    transformation: Optional[str] = Field(default=None, description="Optional transformation hint")
    validation_status: str = Field(..., description="Validation status: pass/warn/fail")
    validation_notes: List[str] = Field(default_factory=list, description="Validation notes")
    created_at: datetime = Field(..., description="Row creation timestamp")


class MappingSessionRead(BaseModel):
    """Summary of a mapping session (no field-mappings included).

    Attributes:
        id: Primary key.
        customer_id: FK to ``user.id``.
        source: Source CRM identifier (e.g. ``salesforce``).
        source_object: Source object name (e.g. ``Lead``).
        destination_type: Destination schema id.
        status: Pipeline status.
        mapping_kind: ``canonical`` or ``projection``.
        canonical_session_id: For projection runs, the parent canonical session.
        created_at: When the run started.
    """

    id: int = Field(..., description="Mapping-session primary key")
    customer_id: int = Field(..., description="Owning user id")
    source: str = Field(..., description="Source CRM identifier")
    source_object: str = Field(..., description="Source object name")
    destination_type: str = Field(..., description="Destination schema id")
    status: str = Field(..., description="Pipeline status")
    mapping_kind: str = Field(..., description="Either 'canonical' or 'projection'")
    canonical_session_id: Optional[int] = Field(
        default=None,
        description="For projection runs, the parent canonical session id",
    )
    created_at: datetime = Field(..., description="When the run was created")


class MappingSessionDetail(MappingSessionRead):
    """A mapping session with its nested field-mapping rows.

    Attributes:
        field_mappings: List of proposed source->destination field mappings.
    """

    field_mappings: List[FieldMappingRead] = Field(
        default_factory=list,
        description="Proposed source->destination field mappings",
    )


class MappingSessionListResponse(BaseResponse):
    """Paginated list of mapping-session summaries.

    Attributes:
        items: Page of session summaries.
        total: Total number of matching sessions for this user.
        limit: Page size used.
        offset: Page offset used.
    """

    items: List[MappingSessionRead] = Field(default_factory=list, description="Page of session summaries")
    total: int = Field(..., description="Total number of matching sessions")
    limit: int = Field(..., description="Page size used")
    offset: int = Field(..., description="Page offset used")
