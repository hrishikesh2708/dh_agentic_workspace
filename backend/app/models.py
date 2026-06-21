"""All SQLModel table definitions in one place.

Dependency order (top → bottom):
  DatahashSchema
  → Connector
  → User → Session
  → Project
  → MappingSession → FieldMapping → MappingEmbedding
  → OAuthPending, ProjectConnection
  → ProjectConnectionSecret, ProjectSourceModule
  → ProjectFieldMapping, ProjectIntegration
"""

# ruff: noqa: D101, D102

from datetime import UTC, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

import bcrypt
from sqlalchemy import Index, JSON
from sqlmodel import Column, Field, Relationship, SQLModel, UniqueConstraint

# ---------------------------------------------------------------------------
# Users & sessions
# ---------------------------------------------------------------------------


class User(SQLModel, table=True):
    __tablename__ = "user"  # type: ignore[assignment]

    id: int = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    username: Optional[str] = Field(default=None)
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Session defined after User — forward ref required
    sessions: List["Session"] = Relationship(back_populates="user")

    def verify_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), self.hashed_password.encode("utf-8"))

    @staticmethod
    def hash_password(password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


class Session(SQLModel, table=True):
    __tablename__ = "session"  # type: ignore[assignment]

    # id IS the LangGraph thread_id
    id: str = Field(primary_key=True)
    project_id: UUID = Field(foreign_key="project.id", index=True)  # always required
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(default="")
    status: str = Field(default="active", nullable=False)  # active | completed | abandoned
    last_active_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    user: User = Relationship(back_populates="sessions")


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    crm = "crm"
    database = "database"
    warehouse = "warehouse"
    file = "file"


class Source(SQLModel, table=True):
    __tablename__ = "source"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("name", name="uq_source_name"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(nullable=False)  # e.g. "salesforce"
    type: SourceType  # crm | database | warehouse | file
    display_name: str = Field(nullable=False)  # e.g. "Salesforce"
    is_active: bool = Field(default=False, nullable=False)
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Destination registry
# ---------------------------------------------------------------------------


class DestinationStatus(str, Enum):
    active = "active"
    disabled = "disabled"


class Destination(SQLModel, table=True):
    __tablename__ = "destination"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("name", name="uq_destination_name"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(nullable=False)
    channel_group: str = Field(nullable=False)
    channel_display_name: str = Field(nullable=False)
    display_name: str = Field(nullable=False)
    icon_url: Optional[str] = Field(default=None)
    status: DestinationStatus = Field(default=DestinationStatus.disabled, nullable=False)
    is_event_destination: bool = Field(default=False, nullable=False)
    supported_signal_types: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    match_keys: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    per_stage_config: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    required_metadata: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    schema_mappings: List["DestinationSchemaMapping"] = Relationship(back_populates="destination")


# ---------------------------------------------------------------------------
# Datahash Internal Schema
# ---------------------------------------------------------------------------


class DatahashSchemaCategory(str, Enum):
    identity = "identity"
    monetary = "monetary"
    ad_identifier = "ad_identifier"
    consent = "consent"
    cart = "cart"
    event = "event"
    product = "product"


class DatahashSchema(SQLModel, table=True):
    __tablename__ = "datahash_schema"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("canonical_key", name="uq_datahash_canonical_key"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    canonical_key: str = Field(index=True, nullable=False)
    type: str
    category: DatahashSchemaCategory
    label: str
    display_label: str
    hint: Optional[str] = Field(default=None)
    enum_values: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    match_reason: Optional[str] = Field(default=None)
    is_per_stage: bool = Field(default=False, nullable=False)
    allow_constant: bool = Field(default=False, nullable=False)
    accepted_sf_types: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    is_pii: bool = Field(default=False, nullable=False)
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DestinationSchemaMapping(SQLModel, table=True):
    __tablename__ = "destination_schema_mapping"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("destination_id", "field_name", name="uq_destination_schema_mapping"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    destination_id: int = Field(foreign_key="destination.id", nullable=False)
    datahash_schema_id: int = Field(foreign_key="datahash_schema.id", nullable=False, index=True)
    field_name: str = Field(nullable=False)
    is_required: bool = Field(default=False, nullable=False)
    is_recommended: bool = Field(default=False, nullable=False)
    transform_function: Optional[str] = Field(default=None)
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    destination: Destination = Relationship(back_populates="schema_mappings")
    schema_field: "DatahashSchema" = Relationship()


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class Project(SQLModel, table=True):
    __tablename__ = "project"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_project_user_name"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str
    description: Optional[str] = Field(default=None)
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    user: User = Relationship()


# ---------------------------------------------------------------------------
# OAuth & connections
# ---------------------------------------------------------------------------


class ProjectConnectionType(str, Enum):
    source = "source"
    destination = "destination"


class ProjectConnectionStatus(str, Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"


class OAuthPending(SQLModel, table=True):
    __tablename__ = "oauth_pending"  # type: ignore[assignment]
    __table_args__ = (
        Index("ix_oauth_pending_project_id", "project_id"),
        Index("ix_oauth_pending_source_id", "source_id"),
        Index("ix_oauth_pending_destination_id", "destination_id"),
    )

    state: str = Field(primary_key=True)
    project_id: UUID = Field(foreign_key="project.id", nullable=False)
    session_id: str = Field(foreign_key="session.id", nullable=False)
    connection_type: ProjectConnectionType = Field(nullable=False)
    source_id: Optional[int] = Field(default=None, foreign_key="source.id")
    destination_id: Optional[int] = Field(default=None, foreign_key="destination.id")
    pkce_verifier: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProjectConnection(SQLModel, table=True):
    __tablename__ = "project_connection"  # type: ignore[assignment]

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(foreign_key="project.id", index=True)
    connection_type: ProjectConnectionType = Field(nullable=False)
    source_id: Optional[int] = Field(default=None, foreign_key="source.id", index=True)
    destination_id: Optional[int] = Field(default=None, foreign_key="destination.id", index=True)
    status: ProjectConnectionStatus = Field(default=ProjectConnectionStatus.active, nullable=False)
    connection_metadata: Optional[dict] = Field(default=None, sa_column=Column("metadata", JSON))
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    project: Project = Relationship()
    source: Optional["Source"] = Relationship()
    destination: Optional["Destination"] = Relationship()
    # Defined after — forward refs required
    secrets: List["ProjectConnectionSecret"] = Relationship(back_populates="connection")
    source_modules: List["ProjectSourceModule"] = Relationship(back_populates="connection")


class ProjectConnectionSecret(SQLModel, table=True):
    __tablename__ = "project_connection_secret"  # type: ignore[assignment]
    __table_args__ = (
        UniqueConstraint("project_connection_id", "secret_key", name="uq_connection_secret_key"),
        Index("ix_project_connection_secret_conn_id", "project_connection_id"),
    )

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    project_connection_id: UUID = Field(foreign_key="project_connection.id")
    secret_key: str
    secret_value: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    connection: ProjectConnection = Relationship(back_populates="secrets")


# ---------------------------------------------------------------------------
# Project source modules, field mappings, integrations
# ---------------------------------------------------------------------------


class SourceModuleStatus(str, Enum):
    draft = "draft"
    active = "active"
    paused = "paused"


class ProjectSourceModule(SQLModel, table=True):
    __tablename__ = "project_source_module"  # type: ignore[assignment]
    __table_args__ = (
        UniqueConstraint("project_connection_id", "source_object", name="uq_source_module_object"),
        Index("ix_source_module_conn_id", "project_connection_id"),
    )

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    project_connection_id: UUID = Field(foreign_key="project_connection.id")
    source_object: str = Field(nullable=False)
    display_name: Optional[str] = Field(default=None)
    signal_type: Optional[str] = Field(default=None)
    status: SourceModuleStatus = Field(default=SourceModuleStatus.draft, nullable=False)
    schema_snapshot: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON))
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    connection: ProjectConnection = Relationship(back_populates="source_modules")
    # Defined after — forward refs required
    field_mappings: List["ProjectFieldMapping"] = Relationship(back_populates="source_module")
    integrations: List["ProjectIntegration"] = Relationship(back_populates="source_module")


class ProjectFieldMapping(SQLModel, table=True):
    __tablename__ = "project_field_mapping"  # type: ignore[assignment]
    __table_args__ = (
        UniqueConstraint("source_module_id", "datahash_schema_id", name="uq_module_schema_mapping"),
        Index("ix_project_field_mapping_module_id", "source_module_id"),
        Index("ix_project_field_mapping_schema_id", "datahash_schema_id"),
    )

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    source_module_id: UUID = Field(foreign_key="project_source_module.id", nullable=False)
    datahash_schema_id: int = Field(foreign_key="datahash_schema.id", nullable=False)
    source_field_path: Optional[str] = Field(default=None)
    is_constant: bool = Field(default=False, nullable=False)
    constant_value: Optional[str] = Field(default=None)
    is_tombstone: bool = Field(default=False, nullable=False)
    confidence: Optional[float] = Field(default=None)
    confirmed_by: Optional[str] = Field(default=None)
    confirmed_at: Optional[datetime] = Field(default=None)
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    source_module: ProjectSourceModule = Relationship(back_populates="field_mappings")
    schema_field: DatahashSchema = Relationship()


class IntegrationStatus(str, Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    failed = "failed"


class IntegrationCreatedVia(str, Enum):
    copilot = "copilot"
    manual = "manual"


class ProjectIntegration(SQLModel, table=True):
    __tablename__ = "project_integration"  # type: ignore[assignment]
    __table_args__ = (
        UniqueConstraint("source_module_id", "destination_conn_id", "destination_id", name="uq_integration"),
        Index("ix_project_integration_module_id", "source_module_id"),
        Index("ix_project_integration_dest_conn_id", "destination_conn_id"),
    )

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    source_module_id: UUID = Field(foreign_key="project_source_module.id", nullable=False)
    destination_conn_id: UUID = Field(foreign_key="project_connection.id", nullable=False)
    destination_id: int = Field(foreign_key="destination.id", nullable=False)
    status: IntegrationStatus = Field(default=IntegrationStatus.draft, nullable=False)
    created_via: IntegrationCreatedVia = Field(default=IntegrationCreatedVia.copilot, nullable=False)
    activated_at: Optional[datetime] = Field(default=None)
    activated_by: Optional[str] = Field(default=None)
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    source_module: ProjectSourceModule = Relationship(back_populates="integrations")
    destination_connection: ProjectConnection = Relationship()
    destination: Destination = Relationship()


# ---------------------------------------------------------------------------
# Funnel stages, connector config, audit log
# ---------------------------------------------------------------------------


class ProjectFunnelStage(SQLModel, table=True):
    __tablename__ = "project_funnel_stage"  # type: ignore[assignment]
    __table_args__ = (
        UniqueConstraint("source_module_id", "stage_order", name="uq_funnel_stage_order"),
        Index("ix_funnel_stage_module_id", "source_module_id"),
    )

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    source_module_id: UUID = Field(foreign_key="project_source_module.id", nullable=False)
    stage_order: int = Field(nullable=False)
    stage_name: str = Field(nullable=False)
    trigger_field: Optional[str] = Field(default=None)
    trigger_value: Optional[str] = Field(default=None)
    time_field: Optional[str] = Field(default=None)
    value_field: Optional[str] = Field(default=None)
    per_destination: dict = Field(default_factory=dict, sa_column=Column(JSON))
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    source_module: ProjectSourceModule = Relationship()


class ConnectorConfigStatus(str, Enum):
    active = "active"
    superseded = "superseded"


class ConnectorConfig(SQLModel, table=True):
    __tablename__ = "connector_config"  # type: ignore[assignment]
    __table_args__ = (
        Index("ix_connector_config_project_id", "project_id"),
        Index("ix_connector_config_module_id", "source_module_id"),
        Index("ix_connector_config_active_lookup", "project_id", "source_module_id", "status"),
    )

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(foreign_key="project.id", nullable=False)
    source_module_id: UUID = Field(foreign_key="project_source_module.id", nullable=False)
    config_version: int = Field(default=1, nullable=False)
    status: ConnectorConfigStatus = Field(default=ConnectorConfigStatus.active, nullable=False)
    config_hash: str = Field(nullable=False)
    config: dict = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    project: Project = Relationship()
    source_module: ProjectSourceModule = Relationship()


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"  # type: ignore[assignment]
    __table_args__ = (
        Index("ix_audit_log_project_id", "project_id"),
        Index("ix_audit_log_module_id", "source_module_id"),
    )

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(foreign_key="project.id", nullable=False)
    source_module_id: Optional[UUID] = Field(default=None, foreign_key="project_source_module.id")
    action: str = Field(nullable=False)
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    project: Project = Relationship()
    source_module: Optional[ProjectSourceModule] = Relationship()


# ---------------------------------------------------------------------------
# Convenience re-exports
# ---------------------------------------------------------------------------

__all__ = [
    "FieldCategory",
    "IntegrationCreatedVia",
    "IntegrationStatus",
    "ProjectConnectionStatus",
    "SourceModuleStatus",
    "DatahashSchema",
    "DatahashSchemaCategory",
    "Source",
    "SourceType",
    "OAuthPending",
    "Project",
    "ProjectConnection",
    "ProjectConnectionSecret",
    "ProjectFieldMapping",
    "ProjectFunnelStage",
    "ProjectIntegration",
    "ProjectSourceModule",
    "AuditLog",
    "ConnectorConfig",
    "ConnectorConfigStatus",
    "Session",
    "User",
]


class FieldCategory(str, Enum):
    identity = "identity"
    monetary = "monetary"
    ad_identifier = "ad_identifier"
    consent = "consent"
    cart = "cart"
    event = "event"
    product = "product"
