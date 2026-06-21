# ruff: noqa: D101, D102
"""SQLModel ORM models for the Datahash backend.

Table dependency order (top → bottom mirrors FK dependency):
  User → Session
  Source
  Destination → DestinationSchemaMapping ← DatahashSchema
  Project ← Session (FK only, no ORM back-ref on Project)
  ProjectConnection ← OAuthPending
  ProjectConnection ← ProjectConnectionSecret
  ProjectConnection ← ProjectSourceModule ← ProjectFieldMapping
  ProjectSourceModule ← ProjectIntegration
  ProjectSourceModule ← ProjectFunnelStage
  ProjectSourceModule ← ConnectorConfig
  Project ← AuditLog
"""

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

    sessions: List["Session"] = Relationship(back_populates="user")

    def verify_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), self.hashed_password.encode("utf-8"))

    @staticmethod
    def hash_password(password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


class Session(SQLModel, table=True):
    """Agent session — id doubles as the LangGraph thread_id."""

    __tablename__ = "session"  # type: ignore[assignment]

    id: str = Field(primary_key=True)  # LangGraph thread_id
    project_id: UUID = Field(foreign_key="project.id", index=True)
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
    name: str = Field(nullable=False)  # slug used in code, e.g. "salesforce"
    display_name: str = Field(nullable=False)  # human label, e.g. "Salesforce"
    type: SourceType = Field(nullable=False)
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
    name: str = Field(nullable=False)  # slug, e.g. "meta_capi"
    display_name: str = Field(nullable=False)  # e.g. "Meta Conversions API"
    channel_group: str = Field(nullable=False)
    channel_display_name: str = Field(nullable=False)
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
# Canonical (Datahash) schema
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
    label: str = Field(nullable=False)
    display_label: str = Field(nullable=False)
    type: str = Field(nullable=False)
    category: DatahashSchemaCategory = Field(nullable=False)
    hint: Optional[str] = Field(default=None)
    enum_values: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    match_reason: Optional[str] = Field(default=None)
    accepted_sf_types: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    is_per_stage: bool = Field(default=False, nullable=False)
    allow_constant: bool = Field(default=False, nullable=False)
    is_pii: bool = Field(default=False, nullable=False)
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DestinationSchemaMapping(SQLModel, table=True):
    """Maps a destination field to a canonical DatahashSchema field."""

    __tablename__ = "destination_schema_mapping"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("destination_id", "field_name", name="uq_destination_schema_mapping"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    destination_id: int = Field(foreign_key="destination.id", nullable=False, index=True)
    datahash_schema_id: int = Field(foreign_key="datahash_schema.id", nullable=False, index=True)
    field_name: str = Field(nullable=False)
    is_required: bool = Field(default=False, nullable=False)
    is_recommended: bool = Field(default=False, nullable=False)
    transform_function: Optional[str] = Field(default=None)
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    destination: Destination = Relationship(back_populates="schema_mappings")
    schema_field: DatahashSchema = Relationship()


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class Project(SQLModel, table=True):
    __tablename__ = "project"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_project_user_name"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(nullable=False)
    description: Optional[str] = Field(default=None)
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    user: User = Relationship()


# ---------------------------------------------------------------------------
# OAuth pending & project connections
# ---------------------------------------------------------------------------


class ProjectConnectionType(str, Enum):
    source = "source"
    destination = "destination"


class ProjectConnectionStatus(str, Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"


class OAuthPending(SQLModel, table=True):
    """Short-lived record tracking an in-flight OAuth authorisation flow.

    Exactly one of source_id / destination_id must be non-null (enforced by a
    CHECK constraint added in the Alembic migration).
    """

    __tablename__ = "oauth_pending"  # type: ignore[assignment]

    state: str = Field(primary_key=True)  # CSRF-safe random token
    project_id: UUID = Field(foreign_key="project.id", nullable=False, index=True)
    session_id: str = Field(foreign_key="session.id", nullable=False)
    connection_type: ProjectConnectionType = Field(nullable=False)
    source_id: Optional[int] = Field(default=None, foreign_key="source.id", index=True)
    destination_id: Optional[int] = Field(default=None, foreign_key="destination.id", index=True)
    pkce_verifier: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProjectConnection(SQLModel, table=True):
    """A live connection between a project and a source or destination.

    Exactly one of source_id / destination_id must be non-null (enforced by a
    CHECK constraint added in the Alembic migration).  Partial unique indexes
    (WHERE source_id IS NOT NULL / WHERE destination_id IS NOT NULL) enforce
    one active connection per project per source or destination.
    """

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
    source: Optional[Source] = Relationship()
    destination: Optional[Destination] = Relationship()
    secrets: List["ProjectConnectionSecret"] = Relationship(back_populates="connection")
    source_modules: List["ProjectSourceModule"] = Relationship(back_populates="connection")


class ProjectConnectionSecret(SQLModel, table=True):
    """Encrypted credential pair belonging to a ProjectConnection."""

    __tablename__ = "project_connection_secret"  # type: ignore[assignment]
    __table_args__ = (
        UniqueConstraint("project_connection_id", "secret_key", name="uq_connection_secret_key"),
        Index("ix_project_connection_secret_conn_id", "project_connection_id"),
    )

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    project_connection_id: UUID = Field(foreign_key="project_connection.id", nullable=False)
    secret_key: str = Field(nullable=False)
    secret_value: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    connection: ProjectConnection = Relationship(back_populates="secrets")


# ---------------------------------------------------------------------------
# Source modules, field mappings & integrations
# ---------------------------------------------------------------------------


class SourceModuleStatus(str, Enum):
    draft = "draft"
    active = "active"
    paused = "paused"


class ProjectSourceModule(SQLModel, table=True):
    """One Salesforce object (or equivalent) being synced through a source connection.

    source_object stores the API name exactly as the source system uses it,
    e.g. "Opportunity", "Lead", "Contact", "Custom_Object__c".
    """

    __tablename__ = "project_source_module"  # type: ignore[assignment]
    __table_args__ = (
        UniqueConstraint("project_connection_id", "source_object", name="uq_source_module_object"),
        Index("ix_source_module_conn_id", "project_connection_id"),
    )

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    project_connection_id: UUID = Field(foreign_key="project_connection.id", nullable=False)
    source_object: str = Field(nullable=False)  # Salesforce API name, e.g. "Opportunity"
    display_name: Optional[str] = Field(default=None)
    signal_type: Optional[str] = Field(default=None)
    status: SourceModuleStatus = Field(default=SourceModuleStatus.draft, nullable=False)
    schema_snapshot: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON))
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    connection: ProjectConnection = Relationship(back_populates="source_modules")
    field_mappings: List["ProjectFieldMapping"] = Relationship(back_populates="source_module")
    integrations: List["ProjectIntegration"] = Relationship(back_populates="source_module")


class ProjectFieldMapping(SQLModel, table=True):
    """Maps one source field to one canonical DatahashSchema field for a module."""

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
    confidence: Optional[float] = Field(default=None)
    confirmed_by: Optional[str] = Field(default=None)
    confirmed_at: Optional[datetime] = Field(default=None)
    is_tombstone: bool = Field(default=False, nullable=False)  # soft-overridden by a later mapping
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
    """Activated pipeline: a source module → a destination connection."""

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
# Funnel stages, connector config snapshots, audit log
# ---------------------------------------------------------------------------


class ProjectFunnelStage(SQLModel, table=True):
    """Ordered conversion funnel stage for a source module."""

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
    """Versioned, immutable config snapshot for a source module.

    When config changes, the previous row is set to superseded and a new row
    (config_version + 1) is inserted.
    """

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
    """Append-only audit trail for project-level actions."""

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
# Public API surface
# ---------------------------------------------------------------------------

__all__ = [
    # Enums
    "ConnectorConfigStatus",
    "DatahashSchemaCategory",
    "DestinationStatus",
    "IntegrationCreatedVia",
    "IntegrationStatus",
    "ProjectConnectionStatus",
    "ProjectConnectionType",
    "SourceModuleStatus",
    "SourceType",
    # Models — registry
    "DatahashSchema",
    "Destination",
    "DestinationSchemaMapping",
    "Source",
    # Models — auth / session
    "Session",
    "User",
    # Models — projects
    "Project",
    # Models — connections
    "OAuthPending",
    "ProjectConnection",
    "ProjectConnectionSecret",
    # Models — pipelines
    "ProjectSourceModule",
    "ProjectFieldMapping",
    "ProjectIntegration",
    "ProjectFunnelStage",
    # Models — config & audit
    "AuditLog",
    "ConnectorConfig",
]
