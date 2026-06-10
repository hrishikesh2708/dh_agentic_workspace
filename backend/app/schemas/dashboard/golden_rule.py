"""Pydantic schemas for golden-rule dashboard endpoints."""

from datetime import datetime
from typing import List

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

from app.schemas.base import BaseResponse


class GoldenRuleRead(BaseModel):
    """A learned mapping rule.

    Attributes:
        id: Primary key.
        source_pattern: Lowercased source field name (or pattern).
        destination_field: The destination field this pattern maps to.
        destination_type: Which destination schema this rule applies to.
        occurrence_count: Number of times the pair has been confirmed.
        created_at: When the rule was first recorded.
    """

    id: int = Field(..., description="Golden-rule primary key")
    source_pattern: str = Field(..., description="Lowercased source field pattern")
    destination_field: str = Field(..., description="Destination field the pattern maps to")
    destination_type: str = Field(..., description="Destination schema id")
    occurrence_count: int = Field(..., description="How many times this rule has been confirmed")
    created_at: datetime = Field(..., description="Row creation timestamp")


class GoldenRuleCreate(BaseModel):
    """Request body for manually adding a golden rule.

    Attributes:
        source_pattern: Lowercased source field pattern.
        destination_field: Destination field this pattern maps to.
        destination_type: Which destination schema this rule applies to.
        occurrence_count: Initial occurrence count (defaults to 1).
    """

    source_pattern: str = Field(..., min_length=1, max_length=255, description="Source field pattern")
    destination_field: str = Field(..., min_length=1, max_length=255, description="Destination field")
    destination_type: str = Field(..., min_length=1, max_length=255, description="Destination schema id")
    occurrence_count: int = Field(default=1, ge=1, description="Initial occurrence count")

    @field_validator("source_pattern")
    @classmethod
    def lower_source_pattern(cls, v: str) -> str:
        """Normalise the source pattern to lowercase to match learner output."""
        return v.strip().lower()

    @field_validator("destination_field", "destination_type")
    @classmethod
    def strip_value(cls, v: str) -> str:
        """Trim leading / trailing whitespace."""
        return v.strip()


class GoldenRuleListResponse(BaseResponse):
    """Paginated list of golden rules.

    Attributes:
        items: Page of golden rules.
        total: Total number of matching rules.
        limit: Page size used.
        offset: Page offset used.
    """

    items: List[GoldenRuleRead] = Field(default_factory=list, description="Page of golden rules")
    total: int = Field(..., description="Total number of matching rules")
    limit: int = Field(..., description="Page size used")
    offset: int = Field(..., description="Page offset used")
