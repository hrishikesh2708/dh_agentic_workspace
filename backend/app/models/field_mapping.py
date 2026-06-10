"""``field_mapping`` table — one source→destination proposal."""

from typing import (
    TYPE_CHECKING,
    List,
    Optional,
)

from sqlalchemy import JSON
from sqlmodel import (
    Column,
    Field,
    Relationship,
)

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.mapping_embedding import MappingEmbedding
    from app.models.mapping_session import MappingSession


class FieldMapping(BaseModel, table=True):
    """One proposed mapping inside a session.

    Attributes:
        id: Auto-increment primary key.
        session_id: FK to ``mapping_session.id``.
        source_field: The source-side field name.
        destination_field: The destination-side field name (nullable for
            unmatched proposals).
        confidence: 0.0–1.0 LLM/penalty-adjusted score.
        status: Lifecycle — ``auto_approved``, ``needs_review``, ``unmatched``,
            ``human_approved``, ``human_corrected``.
        reasoning: LLM-provided rationale.
        transformation: Optional transformation hint.
        validation_status: ``pass`` / ``warn`` / ``fail``.
        validation_notes: List of validation messages (JSON column).
    """

    __tablename__ = "field_mapping"  # type: ignore[assignment]

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="mapping_session.id", index=True)
    source_field: str = Field(max_length=255, index=True)
    destination_field: Optional[str] = Field(default=None, max_length=255)
    confidence: float = Field(default=0.0)
    status: str = Field(default="needs_review", max_length=64)
    reasoning: str = Field(default="")
    transformation: Optional[str] = Field(default=None)
    validation_status: str = Field(default="pass", max_length=32)
    validation_notes: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    session: "MappingSession" = Relationship(back_populates="mappings")
    embedding: Optional["MappingEmbedding"] = Relationship(
        back_populates="field_mapping",
        sa_relationship_kwargs={"uselist": False},
    )
