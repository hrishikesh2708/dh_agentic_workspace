"""``project_integration`` table — source module → destination fan-out."""

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
    from app.models.connector import Connector
    from app.models.project_connection import ProjectConnection
    from app.models.project_source_module import ProjectSourceModule


class IntegrationStatus(str, Enum):
    """Lifecycle state of a source-to-destination integration."""

    draft = "draft"
    active = "active"
    paused = "paused"
    failed = "failed"


class IntegrationCreatedVia(str, Enum):
    """How the integration was created."""

    copilot = "copilot"
    manual = "manual"


class ProjectIntegration(SQLModel, table=True):
    """Destination fan-out for a configured source module (Copilot §7.9).

    One row per source_module × destination_connection × sub_destination.

    Attributes:
        id: UUID primary key.
        source_module_id: FK to ``project_source_module.id``.
        destination_conn_id: FK to destination ``project_connection.id``.
        sub_destination_slug: FK to ``connector.connector_slug``.
        status: ``draft``, ``active``, ``paused``, or ``failed``.
        created_via: Provenance tag (``copilot`` or ``manual``).
        activated_at: When the integration went live.
        activated_by: User id who activated it.
    """

    __tablename__ = "project_integration"  # type: ignore[assignment]
    __table_args__ = (
        UniqueConstraint(
            "source_module_id",
            "destination_conn_id",
            "sub_destination_slug",
            name="uq_integration",
        ),
    )

    id: Optional[UUID] = Field(default=None, primary_key=True)
    source_module_id: UUID = Field(foreign_key="project_source_module.id", index=True)
    destination_conn_id: UUID = Field(foreign_key="project_connection.id", index=True)
    sub_destination_slug: str = Field(foreign_key="connector.connector_slug")
    status: IntegrationStatus = Field(default=IntegrationStatus.draft)
    created_via: IntegrationCreatedVia = Field(default=IntegrationCreatedVia.copilot)
    activated_at: Optional[datetime] = Field(default=None)
    activated_by: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    source_module: "ProjectSourceModule" = Relationship(back_populates="integrations")
    destination_connection: "ProjectConnection" = Relationship()
    sub_destination: "Connector" = Relationship()
