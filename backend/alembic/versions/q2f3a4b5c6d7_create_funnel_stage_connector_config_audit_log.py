"""Create project_funnel_stage, connector_config, and audit_log tables.

Revision ID: q2f3a4b5c6d7
Revises: p1e2f3a4b5c6
Create Date: 2026-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "p1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_funnel_stage",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_module_id", sa.UUID(), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("stage_name", sa.Text(), nullable=False),
        sa.Column("trigger_field", sa.Text(), nullable=True),
        sa.Column("trigger_value", sa.Text(), nullable=True),
        sa.Column("time_field", sa.Text(), nullable=True),
        sa.Column("value_field", sa.Text(), nullable=True),
        sa.Column("per_destination", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_module_id"], ["project_source_module.id"], name="fk_funnel_stage_module_id"),
        sa.UniqueConstraint("source_module_id", "stage_order", name="uq_funnel_stage_order"),
    )
    op.create_index("ix_funnel_stage_module_id", "project_funnel_stage", ["source_module_id"])

    op.create_table(
        "connector_config",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("source_module_id", sa.UUID(), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("config_hash", sa.Text(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], name="fk_connector_config_project_id"),
        sa.ForeignKeyConstraint(
            ["source_module_id"], ["project_source_module.id"], name="fk_connector_config_module_id"
        ),
    )
    op.create_index("ix_connector_config_project_id", "connector_config", ["project_id"])
    op.create_index("ix_connector_config_module_id", "connector_config", ["source_module_id"])
    op.create_index(
        "ix_connector_config_active_lookup", "connector_config", ["project_id", "source_module_id", "status"]
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("source_module_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], name="fk_audit_log_project_id"),
        sa.ForeignKeyConstraint(["source_module_id"], ["project_source_module.id"], name="fk_audit_log_module_id"),
    )
    op.create_index("ix_audit_log_project_id", "audit_log", ["project_id"])
    op.create_index("ix_audit_log_module_id", "audit_log", ["source_module_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_module_id", table_name="audit_log")
    op.drop_index("ix_audit_log_project_id", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_connector_config_active_lookup", table_name="connector_config")
    op.drop_index("ix_connector_config_module_id", table_name="connector_config")
    op.drop_index("ix_connector_config_project_id", table_name="connector_config")
    op.drop_table("connector_config")

    op.drop_index("ix_funnel_stage_module_id", table_name="project_funnel_stage")
    op.drop_table("project_funnel_stage")
