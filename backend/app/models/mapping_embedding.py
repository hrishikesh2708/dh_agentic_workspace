"""``mapping_embedding`` table — pgvector embeddings for past mappings."""

from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
)

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON
from sqlmodel import (
    Column,
    Field,
    Relationship,
)

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.field_mapping import FieldMapping

EMBEDDING_DIMENSIONS = 1536


class MappingEmbedding(BaseModel, table=True):
    """pgvector embedding for an approved field mapping.

    Used by the mapper's example-retrieval step (top-k similar past mappings).
    Writes go through raw SQL in :mod:`app.agents.shared_tools.vector_store`
    because pgvector's ``<=>`` operator isn't a first-class SQLAlchemy idiom;
    this model exists for migration generation + relationships.

    Attributes:
        id: Auto-increment primary key.
        field_mapping_id: FK to ``field_mapping.id`` (unique — one embedding
            per mapping).
        embedding: 1536-dim float vector (OpenAI ``text-embedding-3-small``).
        metadata_json: Arbitrary JSON metadata (mapped to a column called
            ``metadata`` since that's a reserved attribute name on SQLModel).
    """

    __tablename__ = "mapping_embedding"  # type: ignore[assignment]

    id: Optional[int] = Field(default=None, primary_key=True)
    field_mapping_id: int = Field(foreign_key="field_mapping.id", unique=True)
    embedding: Any = Field(sa_column=Column(Vector(EMBEDDING_DIMENSIONS), nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column("metadata", JSON))

    field_mapping: "FieldMapping" = Relationship(back_populates="embedding")
