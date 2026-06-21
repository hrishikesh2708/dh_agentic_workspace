"""Initial schema — creates all application tables from scratch.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from alembic import op

revision: str = "0001_initial_schema"  # pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UUID_DEFAULT = sa.text("gen_random_uuid()")
_NOW = sa.text("now()")


def _ts(name: str) -> sa.Column:
    """Timestamptz column with now() default."""
    return sa.Column(name, sa.TIMESTAMP(timezone=True), nullable=False, server_default=_NOW)


def _bool(name: str, default: bool = False) -> sa.Column:
    return sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.text(str(default).lower()))


def _trigger(table: str) -> None:
    """Attach the update_updated_at trigger to a table."""
    op.execute(
        f"""
        CREATE TRIGGER trg_{table}_updated_at
        BEFORE UPDATE ON "{table}"
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        """
    )


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # ── Shared trigger function ──────────────────────────────────────────────
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # ── user ────────────────────────────────────────────────────────────────
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("hashed_password", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("username", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        _bool("is_deleted"),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=True)
    _trigger("user")

    # ── source ───────────────────────────────────────────────────────────────
    op.create_table(
        "source",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),  # crm | database | warehouse | file
        _bool("is_active"),
        _bool("is_deleted"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("name", name="uq_source_name"),
    )
    _trigger("source")

    # ── destination ──────────────────────────────────────────────────────────
    op.create_table(
        "destination",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("channel_group", sa.Text(), nullable=False),
        sa.Column("channel_display_name", sa.Text(), nullable=False),
        sa.Column("icon_url", sa.Text(), nullable=True),
        _bool("is_active"),
        _bool("is_event_destination"),
        sa.Column("supported_signal_types", sa.JSON(), nullable=True),
        sa.Column("match_keys", sa.JSON(), nullable=True),
        sa.Column("per_stage_config", sa.JSON(), nullable=True),
        sa.Column("required_metadata", sa.JSON(), nullable=True),
        _bool("is_deleted"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("name", name="uq_destination_name"),
    )
    _trigger("destination")

    # ── datahash_schema ──────────────────────────────────────────────────────
    op.create_table(
        "datahash_schema",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("canonical_key", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("display_label", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("hint", sa.Text(), nullable=True),
        sa.Column("enum_values", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("accepted_sf_types", sa.JSON(), nullable=False, server_default="[]"),
        _bool("is_per_stage"),
        _bool("allow_constant"),
        _bool("is_pii"),
        _bool("is_deleted"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("canonical_key", name="uq_datahash_canonical_key"),
    )
    op.create_index(op.f("ix_datahash_schema_canonical_key"), "datahash_schema", ["canonical_key"])
    _trigger("datahash_schema")

    # ── destination_schema_mapping ───────────────────────────────────────────
    op.create_table(
        "destination_schema_mapping",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("destination_id", sa.Integer(), nullable=False),
        sa.Column("datahash_schema_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.Text(), nullable=False),
        _bool("is_required"),
        _bool("is_recommended"),
        sa.Column("enum_values", sa.JSON(), nullable=True),
        sa.Column("source_mode_hint", sa.Text(), nullable=True),  # set_at_sync | per_stage | None
        sa.Column("constraints", sa.JSON(), nullable=True),  # e.g. {"hash": "sha256"}
        sa.Column("transform_function", sa.Text(), nullable=True),
        _bool("is_deleted"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["destination_id"], ["destination.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["datahash_schema_id"], ["datahash_schema.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("destination_id", "field_name", name="uq_destination_schema_mapping"),
    )
    op.create_index(
        op.f("ix_destination_schema_mapping_destination_id"), "destination_schema_mapping", ["destination_id"]
    )
    op.create_index(
        op.f("ix_destination_schema_mapping_datahash_schema_id"), "destination_schema_mapping", ["datahash_schema_id"]
    )
    _trigger("destination_schema_mapping")

    # ── project ──────────────────────────────────────────────────────────────
    op.create_table(
        "project",
        sa.Column("id", sa.UUID(), nullable=False, server_default=_UUID_DEFAULT),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        _bool("is_deleted"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("user_id", "name", name="uq_project_user_name"),
    )
    op.create_index(op.f("ix_project_user_id"), "project", ["user_id"])
    _trigger("project")

    # ── session ──────────────────────────────────────────────────────────────
    # id = LangGraph thread_id
    op.create_table(
        "session",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=""),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="active"),
        sa.Column("last_active_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=_NOW),
        _bool("is_deleted"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_session_user_id"), "session", ["user_id"])
    op.create_index(op.f("ix_session_project_id"), "session", ["project_id"])
    _trigger("session")

    # ── project_connection ───────────────────────────────────────────────────
    op.create_table(
        "project_connection",
        sa.Column("id", sa.UUID(), nullable=False, server_default=_UUID_DEFAULT),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("connection_type", sa.Text(), nullable=False),  # source | destination
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("destination_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        _bool("is_deleted"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_id"], ["source.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["destination_id"], ["destination.id"], ondelete="RESTRICT"),
    )
    # Exactly one of source_id / destination_id must be set
    op.execute(
        """
        ALTER TABLE project_connection ADD CONSTRAINT ck_project_connection_source_or_dest
        CHECK (
            (source_id IS NOT NULL AND destination_id IS NULL) OR
            (source_id IS NULL AND destination_id IS NOT NULL)
        )
        """
    )
    # Partial unique indexes — one active connection per project per source/destination
    op.execute(
        """
        CREATE UNIQUE INDEX uq_project_connection_source
        ON project_connection (project_id, source_id)
        WHERE source_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_project_connection_destination
        ON project_connection (project_id, destination_id)
        WHERE destination_id IS NOT NULL
        """
    )
    op.create_index(op.f("ix_project_connection_project_id"), "project_connection", ["project_id"])
    op.create_index(op.f("ix_project_connection_source_id"), "project_connection", ["source_id"])
    op.create_index(op.f("ix_project_connection_destination_id"), "project_connection", ["destination_id"])
    _trigger("project_connection")

    # ── oauth_pending ────────────────────────────────────────────────────────
    op.create_table(
        "oauth_pending",
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("connection_type", sa.Text(), nullable=False),  # source | destination
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("destination_id", sa.Integer(), nullable=True),
        sa.Column("pkce_verifier", sa.Text(), nullable=True),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("state"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["session.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["source.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["destination_id"], ["destination.id"], ondelete="RESTRICT"),
    )
    op.execute(
        """
        ALTER TABLE oauth_pending ADD CONSTRAINT ck_oauth_pending_source_or_dest
        CHECK (
            (source_id IS NOT NULL AND destination_id IS NULL) OR
            (source_id IS NULL AND destination_id IS NOT NULL)
        )
        """
    )
    op.create_index(op.f("ix_oauth_pending_project_id"), "oauth_pending", ["project_id"])
    op.create_index(op.f("ix_oauth_pending_source_id"), "oauth_pending", ["source_id"])
    op.create_index(op.f("ix_oauth_pending_destination_id"), "oauth_pending", ["destination_id"])

    # ── project_connection_secret ────────────────────────────────────────────
    op.create_table(
        "project_connection_secret",
        sa.Column("id", sa.UUID(), nullable=False, server_default=_UUID_DEFAULT),
        sa.Column("project_connection_id", sa.UUID(), nullable=False),
        sa.Column("secret_key", sa.Text(), nullable=False),
        sa.Column("secret_value", sa.Text(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_connection_id"], ["project_connection.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_connection_id", "secret_key", name="uq_connection_secret_key"),
    )
    op.create_index("ix_project_connection_secret_conn_id", "project_connection_secret", ["project_connection_id"])
    _trigger("project_connection_secret")

    # ── project_source_module ────────────────────────────────────────────────
    op.create_table(
        "project_source_module",
        sa.Column("id", sa.UUID(), nullable=False, server_default=_UUID_DEFAULT),
        sa.Column("project_connection_id", sa.UUID(), nullable=False),
        sa.Column("source_object", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("signal_type", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("schema_snapshot", sa.JSON(), nullable=True),
        _bool("is_deleted"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_connection_id"], ["project_connection.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_connection_id", "source_object", name="uq_source_module_object"),
    )
    op.create_index("ix_source_module_conn_id", "project_source_module", ["project_connection_id"])
    _trigger("project_source_module")

    # ── project_field_mapping ────────────────────────────────────────────────
    op.create_table(
        "project_field_mapping",
        sa.Column("id", sa.UUID(), nullable=False, server_default=_UUID_DEFAULT),
        sa.Column("source_module_id", sa.UUID(), nullable=False),
        sa.Column("datahash_schema_id", sa.Integer(), nullable=False),
        sa.Column("source_field_path", sa.Text(), nullable=True),
        _bool("is_constant"),
        sa.Column("constant_value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("confirmed_by", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        _bool("is_tombstone"),
        _bool("is_deleted"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_module_id"], ["project_source_module.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["datahash_schema_id"], ["datahash_schema.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("source_module_id", "datahash_schema_id", name="uq_module_schema_mapping"),
    )
    op.create_index("ix_project_field_mapping_module_id", "project_field_mapping", ["source_module_id"])
    op.create_index("ix_project_field_mapping_schema_id", "project_field_mapping", ["datahash_schema_id"])
    _trigger("project_field_mapping")

    # ── project_integration ──────────────────────────────────────────────────
    op.create_table(
        "project_integration",
        sa.Column("id", sa.UUID(), nullable=False, server_default=_UUID_DEFAULT),
        sa.Column("source_module_id", sa.UUID(), nullable=False),
        sa.Column("destination_conn_id", sa.UUID(), nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("created_via", sa.Text(), nullable=False, server_default="copilot"),
        sa.Column("activated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("activated_by", sa.Text(), nullable=True),
        _bool("is_deleted"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_module_id"], ["project_source_module.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["destination_conn_id"], ["project_connection.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["destination_id"], ["destination.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("source_module_id", "destination_conn_id", "destination_id", name="uq_integration"),
    )
    op.create_index("ix_project_integration_module_id", "project_integration", ["source_module_id"])
    op.create_index("ix_project_integration_dest_conn_id", "project_integration", ["destination_conn_id"])
    _trigger("project_integration")

    # ── project_funnel_stage ─────────────────────────────────────────────────
    op.create_table(
        "project_funnel_stage",
        sa.Column("id", sa.UUID(), nullable=False, server_default=_UUID_DEFAULT),
        sa.Column("source_module_id", sa.UUID(), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("stage_name", sa.Text(), nullable=False),
        sa.Column("trigger_field", sa.Text(), nullable=True),
        sa.Column("trigger_value", sa.Text(), nullable=True),
        sa.Column("time_field", sa.Text(), nullable=True),
        sa.Column("value_field", sa.Text(), nullable=True),
        sa.Column("per_destination", sa.JSON(), nullable=False, server_default="{}"),
        _bool("is_deleted"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_module_id"], ["project_source_module.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("source_module_id", "stage_order", name="uq_funnel_stage_order"),
    )
    op.create_index("ix_funnel_stage_module_id", "project_funnel_stage", ["source_module_id"])
    _trigger("project_funnel_stage")

    # ── connector_config ─────────────────────────────────────────────────────
    op.create_table(
        "connector_config",
        sa.Column("id", sa.UUID(), nullable=False, server_default=_UUID_DEFAULT),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("source_module_id", sa.UUID(), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),  # active | superseded
        sa.Column("config_hash", sa.Text(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_module_id"], ["project_source_module.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_connector_config_project_id", "connector_config", ["project_id"])
    op.create_index("ix_connector_config_module_id", "connector_config", ["source_module_id"])
    op.create_index(
        "ix_connector_config_active_lookup", "connector_config", ["project_id", "source_module_id", "status"]
    )

    # ── audit_log ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(), nullable=False, server_default=_UUID_DEFAULT),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("source_module_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_module_id"], ["project_source_module.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_log_project_id", "audit_log", ["project_id"])
    op.create_index("ix_audit_log_module_id", "audit_log", ["source_module_id"])


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    # Drop in reverse FK dependency order
    op.drop_table("audit_log")
    op.drop_table("connector_config")
    op.drop_table("project_funnel_stage")
    op.drop_table("project_integration")
    op.drop_table("project_field_mapping")
    op.drop_table("project_source_module")
    op.drop_table("project_connection_secret")
    op.drop_table("oauth_pending")
    op.drop_table("project_connection")
    op.drop_table("session")
    op.drop_table("project")
    op.drop_table("destination_schema_mapping")
    op.drop_table("datahash_schema")
    op.drop_table("destination")
    op.drop_table("source")
    op.drop_table("user")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at() CASCADE")
