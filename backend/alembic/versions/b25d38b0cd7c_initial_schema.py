"""Initial schema.

Revision ID: b25d38b0cd7c
Revises:
Create Date: 2026-04-12 17:35:38.132952

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b25d38b0cd7c"  # pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("hashed_password", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("username", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=True)

    op.create_table(
        "session",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("username", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "thread",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "mapping_session",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("source", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("source_object", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("destination_type", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("mapping_kind", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("canonical_session_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["canonical_session_id"], ["mapping_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mapping_session_customer_id"), "mapping_session", ["customer_id"])

    op.create_table(
        "field_mapping",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("source_field", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("destination_field", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("transformation", sa.Text(), nullable=True),
        sa.Column("validation_status", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("validation_notes", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["mapping_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_field_mapping_session_id"), "field_mapping", ["session_id"])
    op.create_index(op.f("ix_field_mapping_source_field"), "field_mapping", ["source_field"])

    op.create_table(
        "mapping_embedding",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("field_mapping_id", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["field_mapping_id"], ["field_mapping.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("field_mapping_id"),
    )

    op.create_table(
        "golden_rule",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_pattern", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("destination_field", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("destination_type", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_golden_rule_source_pattern"), "golden_rule", ["source_pattern"])
    op.create_index(op.f("ix_golden_rule_destination_type"), "golden_rule", ["destination_type"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_golden_rule_destination_type"), table_name="golden_rule")
    op.drop_index(op.f("ix_golden_rule_source_pattern"), table_name="golden_rule")
    op.drop_table("golden_rule")
    op.drop_table("mapping_embedding")
    op.drop_index(op.f("ix_field_mapping_source_field"), table_name="field_mapping")
    op.drop_index(op.f("ix_field_mapping_session_id"), table_name="field_mapping")
    op.drop_table("field_mapping")
    op.drop_index(op.f("ix_mapping_session_customer_id"), table_name="mapping_session")
    op.drop_table("mapping_session")
    op.drop_table("thread")
    op.drop_table("session")
    op.drop_index(op.f("ix_user_email"), table_name="user")
    op.drop_table("user")
