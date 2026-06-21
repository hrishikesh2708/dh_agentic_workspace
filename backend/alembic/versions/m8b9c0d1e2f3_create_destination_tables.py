"""Create destination and destination_schema_mapping tables.

Revision ID: m8b9c0d1e2f3
Revises: l7a8b9c0d1e2
Create Date: 2026-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "l7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "destination",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("channel_group", sa.Text(), nullable=False),
        sa.Column("channel_display_name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("icon_url", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="disabled"),
        sa.Column("is_event_destination", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("supported_signal_types", sa.JSON(), nullable=True),
        sa.Column("match_keys", sa.JSON(), nullable=True),
        sa.Column("per_stage_config", sa.JSON(), nullable=True),
        sa.Column("required_metadata", sa.JSON(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_destination_name"),
    )

    op.create_table(
        "destination_schema_mapping",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("destination_id", sa.Integer(), nullable=False),
        sa.Column("datahash_schema_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.Text(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_recommended", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("transform_function", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["destination_id"], ["destination.id"], name="fk_dsm_destination_id"),
        sa.ForeignKeyConstraint(["datahash_schema_id"], ["datahash_schema.id"], name="fk_dsm_datahash_schema_id"),
        sa.UniqueConstraint("destination_id", "field_name", name="uq_destination_schema_mapping"),
    )
    op.create_index(
        "ix_destination_schema_mapping_schema_id",
        "destination_schema_mapping",
        ["datahash_schema_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_destination_schema_mapping_schema_id", table_name="destination_schema_mapping")
    op.drop_table("destination_schema_mapping")
    op.drop_table("destination")
