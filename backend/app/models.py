"""All SQLModel table definitions in one place.

Dependency order (top → bottom):
  CanonicalField, GoldenRule
  → DestinationFieldMapping
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
from typing import Any, List, Optional
from uuid import UUID, uuid4

import bcrypt
from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON
from sqlmodel import Column, Field, Relationship, SQLModel, UniqueConstraint

EMBEDDING_DIMENSIONS = 1536


# ---------------------------------------------------------------------------
# Standalone / leaf models
# ---------------------------------------------------------------------------


class CanonicalField(SQLModel, table=True):
    __tablename__ = "canonical_field"  # type: ignore[assignment]

    canonical_key: str = Field(primary_key=True)
    field_label: str
    field_hint: Optional[str] = Field(default=None)
    field_category: str = Field(description="identity | monetary | ad_identifier | consent | cart | event | product")
    is_pii: bool = Field(default=False)


class GoldenRule(SQLModel, table=True):
    __tablename__ = "golden_rule"  # type: ignore[assignment]

    id: Optional[int] = Field(default=None, primary_key=True)
    source_pattern: str = Field(max_length=255, index=True)
    destination_field: str = Field(max_length=255)
    destination_type: str = Field(max_length=255, index=True)
    occurrence_count: int = Field(default=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Connector registry
# ---------------------------------------------------------------------------


class ConnectorType(str, Enum):
    source = "source"
    destination = "destination"


class AuthScheme(str, Enum):
    oauth2 = "oauth2"
    api_key = "api_key"  # pragma: allowlist secret
    multi_key = "multi_key"


class ConnectorStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    disabled = "disabled"


class Connector(SQLModel, table=True):
    __tablename__ = "connector"  # type: ignore[assignment]

    connector_slug: str = Field(primary_key=True)
    connector_type: ConnectorType
    display_name: str
    auth_scheme: AuthScheme
    sub_connector_of: Optional[str] = Field(default=None, foreign_key="connector.connector_slug")
    status: ConnectorStatus = Field(default=ConnectorStatus.active)

    # Self-referential — must use string forward ref
    parent: Optional["Connector"] = Relationship(
        sa_relationship_kwargs={
            "remote_side": "Connector.connector_slug",
            "foreign_keys": "[Connector.sub_connector_of]",
        }
    )


class DestinationFieldMapping(SQLModel, table=True):
    __tablename__ = "destination_field_mapping"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("destination_slug", "sub_destination_slug", "destination_field_path"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    destination_slug: str
    sub_destination_slug: str
    destination_field_path: str
    canonical_key: str = Field(foreign_key="canonical_field.canonical_key", index=True)
    transform_function: Optional[str] = Field(default=None)
    is_required: bool = Field(default=False)
    is_destination_specific: bool = Field(default=False)

    canonical_field: CanonicalField = Relationship()


# ---------------------------------------------------------------------------
# Users & sessions
# ---------------------------------------------------------------------------


class User(SQLModel, table=True):
    __tablename__ = "user"  # type: ignore[assignment]

    id: int = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    username: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

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

    id: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    project_id: Optional[UUID] = Field(default=None, foreign_key="project.id", index=True)
    name: str = Field(default="")
    username: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    user: User = Relationship(back_populates="sessions")


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
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    user: User = Relationship()


# ---------------------------------------------------------------------------
# Mapping pipeline (legacy session-based)
# ---------------------------------------------------------------------------


class MappingSession(SQLModel, table=True):
    __tablename__ = "mapping_session"  # type: ignore[assignment]

    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="user.id", index=True)
    source: str = Field(max_length=64)
    source_object: str = Field(max_length=255)
    destination_type: str = Field(max_length=255)
    status: str = Field(default="pending", max_length=64)
    mapping_kind: str = Field(default="canonical", max_length=32)
    canonical_session_id: Optional[int] = Field(default=None, foreign_key="mapping_session.id", nullable=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # FieldMapping defined after — forward ref required
    mappings: List["FieldMapping"] = Relationship(back_populates="session")


class FieldMapping(SQLModel, table=True):
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    session: MappingSession = Relationship(back_populates="mappings")
    # MappingEmbedding defined after — forward ref required
    embedding: Optional["MappingEmbedding"] = Relationship(
        back_populates="field_mapping",
        sa_relationship_kwargs={"uselist": False},
    )


class MappingEmbedding(SQLModel, table=True):
    __tablename__ = "mapping_embedding"  # type: ignore[assignment]

    id: Optional[int] = Field(default=None, primary_key=True)
    field_mapping_id: int = Field(foreign_key="field_mapping.id", unique=True)
    embedding: Any = Field(sa_column=Column(Vector(EMBEDDING_DIMENSIONS), nullable=False))
    metadata_json: dict = Field(default_factory=dict, sa_column=Column("metadata", JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    field_mapping: FieldMapping = Relationship(back_populates="embedding")


# ---------------------------------------------------------------------------
# OAuth & connections
# ---------------------------------------------------------------------------


class OAuthPending(SQLModel, table=True):
    __tablename__ = "oauth_pending"  # type: ignore[assignment]

    state: str = Field(primary_key=True)
    connector_slug: str = Field(index=True)
    project_id: UUID = Field(foreign_key="project.id", index=True)
    session_id: str
    pkce_verifier: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProjectConnectionStatus(str, Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"


class ProjectConnection(SQLModel, table=True):
    __tablename__ = "project_connection"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("project_id", "connector_slug", name="uq_project_connector"),)

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    project_id: UUID = Field(foreign_key="project.id", index=True)
    connector_slug: str = Field(foreign_key="connector.connector_slug")
    status: ProjectConnectionStatus = Field(default=ProjectConnectionStatus.active)
    connection_metadata: Optional[dict] = Field(default=None, sa_column=Column("metadata", JSON))
    connected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    connected_by: Optional[str] = Field(default=None)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    project: Project = Relationship()
    connector: Connector = Relationship()
    # Defined after — forward refs required
    secrets: List["ProjectConnectionSecret"] = Relationship(back_populates="connection")
    source_modules: List["ProjectSourceModule"] = Relationship(back_populates="connection")


class ProjectConnectionSecret(SQLModel, table=True):
    __tablename__ = "project_connection_secret"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("project_connection_id", "secret_key", name="uq_connection_secret_key"),)

    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    project_connection_id: UUID = Field(foreign_key="project_connection.id", index=True)
    secret_key: str
    secret_value: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    connection: ProjectConnection = Relationship(back_populates="secrets")


# ---------------------------------------------------------------------------
# Project source modules, field mappings, integrations
# ---------------------------------------------------------------------------


class SourceModuleType(str, Enum):
    leads = "leads"
    opportunities = "opportunities"
    contacts = "contacts"
    custom_object = "custom_object"
    table = "table"
    file = "file"


class SourceModuleStatus(str, Enum):
    draft = "draft"
    active = "active"
    paused = "paused"


class ProjectSourceModule(SQLModel, table=True):
    __tablename__ = "project_source_module"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("project_connection_id", "module_identifier", name="uq_source_module"),)

    id: Optional[UUID] = Field(default=None, primary_key=True)
    project_connection_id: UUID = Field(foreign_key="project_connection.id", index=True)
    module_type: SourceModuleType
    module_identifier: str
    display_name: Optional[str] = Field(default=None)
    status: SourceModuleStatus = Field(default=SourceModuleStatus.draft)
    schema_snapshot: Optional[List[dict]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    connection: ProjectConnection = Relationship(back_populates="source_modules")
    # Defined after — forward refs required
    field_mappings: List["ProjectFieldMapping"] = Relationship(back_populates="source_module")
    integrations: List["ProjectIntegration"] = Relationship(back_populates="source_module")


class MappingConfidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ProjectFieldMapping(SQLModel, table=True):
    __tablename__ = "project_field_mapping"  # type: ignore[assignment]
    __table_args__ = (UniqueConstraint("source_module_id", "canonical_key", name="uq_module_canonical_key"),)

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

    source_module: ProjectSourceModule = Relationship(back_populates="field_mappings")
    canonical_field: CanonicalField = Relationship()


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
        UniqueConstraint("source_module_id", "destination_conn_id", "sub_destination_slug", name="uq_integration"),
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

    source_module: ProjectSourceModule = Relationship(back_populates="integrations")
    destination_connection: ProjectConnection = Relationship()
    sub_destination: Connector = Relationship()


# ---------------------------------------------------------------------------
# Convenience re-exports
# ---------------------------------------------------------------------------

__all__ = [
    "AuthScheme",
    "ConnectorStatus",
    "ConnectorType",
    "FieldCategory",
    "IntegrationCreatedVia",
    "IntegrationStatus",
    "MappingConfidence",
    "ProjectConnectionStatus",
    "SourceModuleStatus",
    "SourceModuleType",
    "CanonicalField",
    "Connector",
    "DestinationFieldMapping",
    "FieldMapping",
    "GoldenRule",
    "MappingEmbedding",
    "MappingSession",
    "OAuthPending",
    "Project",
    "ProjectConnection",
    "ProjectConnectionSecret",
    "ProjectFieldMapping",
    "ProjectIntegration",
    "ProjectSourceModule",
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
