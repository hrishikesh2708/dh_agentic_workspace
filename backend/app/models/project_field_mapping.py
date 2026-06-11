"""``project_field_mapping`` table — canonical → source field mappings."""

from datetime import (
    UTC,
    datetime,
)
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Optional,
)
from uuid import UUID

from sqlmodel import (
    Field,
    Relationship,
    SQLModel,
    UniqueConstraint,
)

if TYPE_CHECKING:
    from app.models.canonical_field import CanonicalField
    from app.models.project_source_module import ProjectSourceModule


class MappingConfidence(str, Enum):
    """Auto-mapper confidence shown in the Copilot UI."""

    high = "high"
    medium = "medium"
    low = "low"


class ProjectFieldMapping(SQLModel, table=True):
    """User-approved mapping from canonical key to source field path (Copilot §7.7).

    One row per canonical field per source module.

    Attributes:
        id: UUID primary key.
        source_module_id: FK to ``project_source_module.id``.
        canonical_key: FK to ``canonical_field.canonical_key``.
        source_field_path: Path in the source schema; NULL when ``is_constant``.
        is_constant: True when the value is hardcoded (e.g. currency = USD).
        constant_value: Hardcoded value when ``is_constant`` is true.
        confidence: Auto-mapper confidence (high / medium / low).
        confirmed_by: User id who approved the mapping.
        confirmed_at: When the mapping was confirmed.
    """

    __tablename__ = "project_field_mapping"  # type: ignore[assignment]
    __table_args__ = (
        UniqueConstraint(
            "source_module_id",
            "canonical_key",
            name="uq_module_canonical_key",
        ),
    )

    id: Optional[UUID] = Field(default=None, primary_key=True)
    source_module_id: UUID = Field(foreign_key="project_source_module.id", index=True)
    canonical_key: str = Field(foreign_key="canonical_field.canonical_key")
    source_field_path: Optional[str] = Field(default=None)
    is_constant: bool = Field(default=False)
    constant_value: Optional[str] = Field(default=None)
    confidence: Optional[MappingConfidence] = Field(default=None)
    confirmed_by: Optional[str] = Field(default=None)
    confirmed_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    source_module: "ProjectSourceModule" = Relationship(back_populates="field_mappings")
    canonical_field: "CanonicalField" = Relationship()
