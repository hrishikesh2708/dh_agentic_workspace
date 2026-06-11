"""``project_connection`` table — authenticated connector per project."""

from datetime import (
    UTC,
    datetime,
)
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
)
from uuid import UUID

from sqlalchemy import JSON
from sqlmodel import (
    Column,
    Field,
    Relationship,
    SQLModel,
    UniqueConstraint,
)

if TYPE_CHECKING:
    from app.models.connector import Connector
    from app.models.project import Project
    from app.models.project_connection_secret import ProjectConnectionSecret
    from app.models.project_source_module import ProjectSourceModule


class ProjectConnectionStatus(str, Enum):
    """Lifecycle state of an authenticated project connector."""

    active = "active"
    expired = "expired"
    revoked = "revoked"


class ProjectConnection(SQLModel, table=True):
    """One authenticated connector instance per project.

    The Copilot checks this before asking a user to connect anything.

    Attributes:
        id: UUID primary key.
        project_id: FK to ``project.id``.
        connector_slug: FK to ``connector.connector_slug``.
        status: ``active``, ``expired``, or ``revoked``.
        connection_metadata: Non-secret context (instance_url, pixel_name, etc.).
        connected_at: When the connection was established.
        connected_by: User id of whoever connected it.
        updated_at: Last modification timestamp; auto-updated by DB trigger.
    """

    __tablename__ = "project_connection"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("project_id", "connector_slug", name="uq_project_connector"),)

    id: Optional[UUID] = Field(default=None, primary_key=True)
    project_id: UUID = Field(foreign_key="project.id", index=True)
    connector_slug: str = Field(foreign_key="connector.connector_slug")
    status: ProjectConnectionStatus = Field(default=ProjectConnectionStatus.active)
    connection_metadata: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column("metadata", JSON),
    )
    connected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    connected_by: Optional[str] = Field(default=None)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    project: "Project" = Relationship()
    connector: "Connector" = Relationship()
    secrets: list["ProjectConnectionSecret"] = Relationship(back_populates="connection")
    source_modules: list["ProjectSourceModule"] = Relationship(back_populates="connection")
