"""``project_source_module`` table — configured source object per connection."""

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
    from app.models.project_connection import ProjectConnection
    from app.models.project_field_mapping import ProjectFieldMapping
    from app.models.project_integration import ProjectIntegration


class SourceModuleType(str, Enum):
    """Kind of object/table/file within a connected source."""

    leads = "leads"
    opportunities = "opportunities"
    contacts = "contacts"
    custom_object = "custom_object"
    table = "table"
    file = "file"


class SourceModuleStatus(str, Enum):
    """Lifecycle state of a configured source module."""

    draft = "draft"
    active = "active"
    paused = "paused"


class ProjectSourceModule(SQLModel, table=True):
    """A CRM object / DB table / file path within a connected source.

    One row per configured module per connection (Copilot §7.4).

    Attributes:
        id: UUID primary key.
        project_connection_id: FK to the source ``project_connection``.
        module_type: Object kind (leads, table, file, etc.).
        module_identifier: Actual name in the source (e.g. ``Opportunity``).
        display_name: Human label confirmed by the user.
        status: ``draft``, ``active``, or ``paused``.
        schema_snapshot: Field list captured at setup time.
    """

    __tablename__ = "project_source_module"  # type: ignore[assignment]
    __table_args__ = (
        UniqueConstraint(
            "project_connection_id",
            "module_identifier",
            name="uq_source_module",
        ),
    )

    id: Optional[UUID] = Field(default=None, primary_key=True)
    project_connection_id: UUID = Field(foreign_key="project_connection.id", index=True)
    module_type: SourceModuleType
    module_identifier: str
    display_name: Optional[str] = Field(default=None)
    status: SourceModuleStatus = Field(default=SourceModuleStatus.draft)
    schema_snapshot: Optional[list[dict[str, Any]]] = Field(
        default=None,
        sa_column=Column(JSON),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    connection: "ProjectConnection" = Relationship(back_populates="source_modules")
    field_mappings: list["ProjectFieldMapping"] = Relationship(back_populates="source_module")
    integrations: list["ProjectIntegration"] = Relationship(back_populates="source_module")
