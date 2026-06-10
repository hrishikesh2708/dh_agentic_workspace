"""``mapping_session`` table — one row per agent run."""

from datetime import datetime
from typing import (
    TYPE_CHECKING,
    List,
    Optional,
)

from sqlmodel import (
    Field,
    Relationship,
)

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.mapping.field_mapping import FieldMapping


class MappingSession(BaseModel, table=True):
    """One mapping run (canonical or projection).

    Attributes:
        id: Auto-increment primary key.
        customer_id: FK to ``user.id`` (kept as ``customer_id`` to match the
            ported pipeline code; the user IS the customer in our tenancy model).
        source: Source CRM identifier (e.g. ``"salesforce"``).
        source_object: Source object name (e.g. ``"Lead"``).
        destination_type: Destination schema id (e.g. ``"canonical"`` or
            ``"meta_capi"``).
        status: Pipeline status, defaults to ``"pending"``.
        mapping_kind: Either ``"canonical"`` or ``"projection"``.
        canonical_session_id: For projection runs, FK to the canonical session
            this projection builds on. Self-referential, nullable.
        created_at: Inherited from BaseModel.
    """

    __tablename__ = "mapping_session"  # type: ignore[assignment]

    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="user.id", index=True)
    source: str = Field(max_length=64)
    source_object: str = Field(max_length=255)
    destination_type: str = Field(max_length=255)
    status: str = Field(default="pending", max_length=64)
    mapping_kind: str = Field(default="canonical", max_length=32)
    canonical_session_id: Optional[int] = Field(
        default=None,
        foreign_key="mapping_session.id",
        nullable=True,
    )

    mappings: List["FieldMapping"] = Relationship(back_populates="session")


# Override the SQLModel default ``created_at`` factory annotation to use a
# datetime-typed column (BaseModel already does this).
_ = datetime
