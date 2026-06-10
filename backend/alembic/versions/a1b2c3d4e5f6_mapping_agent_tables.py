"""mapping agent tables + pgvector extension.

Revision ID: a1b2c3d4e5f6
Revises: b25d38b0cd7c
Create Date: 2026-06-09 23:00:00.000000

Stage 2 of the crawler_agent → datahash_agentic_workspace migration.

Adds:
- ``CREATE EXTENSION IF NOT EXISTS vector`` (pgvector)
- ``mapping_session``    — one row per agent run
- ``field_mapping``      — one source→destination proposal per row
- ``mapping_embedding``  — pgvector embeddings for past mappings
- ``golden_rule``        — learned high-confidence mapping patterns

``mapping_session.customer_id`` foreign-keys to ``user.id``.
"""

from typing import (
    Sequence,
    Union,
)

import sqlalchemy as sa
import sqlmodel  # noqa: F401
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"  # pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = "b25d38b0cd7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # pgvector extension (idempotent — safe to re-run)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- mapping_session ---
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

    # --- field_mapping ---
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

    # --- mapping_embedding ---
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

    # --- golden_rule ---
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
    # pgvector extension is left in place — it may be used by other apps.
