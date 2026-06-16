"""``project_connection_secret`` table — credential storage per connection."""

from datetime import (
    UTC,
    datetime,
)
from typing import (
    TYPE_CHECKING,
    Optional,
)
from uuid import UUID, uuid4

from sqlmodel import (
    Field,
    Relationship,
    SQLModel,
    UniqueConstraint,
)

if TYPE_CHECKING:
    from app.models.project_connection import ProjectConnection


class ProjectConnectionSecret(SQLModel, table=True):
    """One credential key/value pair for a project connection.

    Plaintext for demo — swap ``secret_value`` storage for KMS in prod.

    Attributes:
        id: UUID primary key.
        project_connection_id: FK to ``project_connection.id``.
        secret_key: Credential name (e.g. ``access_token``, ``pixel_id``).
        secret_value: Credential value (TODO: KMS-encrypted ciphertext in prod).
        created_at: Row creation timestamp.
        updated_at: Last modification timestamp; auto-updated by DB trigger.
    """

    __tablename__ = "project_connection_secret"  # type: ignore[assignment]
    __table_args__ = (
        UniqueConstraint(
            "project_connection_id",
            "secret_key",
            name="uq_connection_secret_key",
        ),
    )

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    project_connection_id: UUID = Field(foreign_key="project_connection.id", index=True)
    secret_key: str
    secret_value: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    connection: "ProjectConnection" = Relationship(back_populates="secrets")
