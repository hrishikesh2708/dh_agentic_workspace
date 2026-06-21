"""Update project_field_mapping and project_integration tables.

project_field_mapping:
  - Drop canonical_key FK, replace with datahash_schema_id (int FK → datahash_schema.id)
  - Drop uq_module_canonical_key, add uq_module_schema_mapping
  - Add is_tombstone, is_deleted
  - confidence changes from text enum → float
  - Rename indexes to canonical names

project_integration:
  - Drop sub_destination_slug FK → connector, replace with destination_id (int FK → destination.id)
  - Drop old uq_integration, add new one on (source_module_id, destination_conn_id, destination_id)
  - Add is_deleted
  - Add named indexes

Revision ID: r3a4b5c6d7e8
Revises: q2f3a4b5c6d7
Create Date: 2026-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "q2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── project_field_mapping ────────────────────────────────────────────────

    # Drop old constraint and index
    op.drop_constraint("uq_module_canonical_key", "project_field_mapping", type_="unique")
    op.drop_constraint("project_field_mapping_canonical_key_fkey", "project_field_mapping", type_="foreignkey")
    op.drop_index("ix_project_field_mapping_source_module_id", table_name="project_field_mapping")

    # Drop old column
    op.drop_column("project_field_mapping", "canonical_key")

    # Add new FK column
    op.add_column("project_field_mapping", sa.Column("datahash_schema_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_project_field_mapping_schema_id",
        "project_field_mapping",
        "datahash_schema",
        ["datahash_schema_id"],
        ["id"],
    )
    # Make non-nullable after adding (existing rows will need a backfill in practice)
    op.alter_column("project_field_mapping", "datahash_schema_id", nullable=False)

    # Add new columns
    op.add_column(
        "project_field_mapping", sa.Column("is_tombstone", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "project_field_mapping", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false")
    )

    # confidence: drop old text column, add float column
    op.drop_column("project_field_mapping", "confidence")
    op.add_column("project_field_mapping", sa.Column("confidence", sa.Float(), nullable=True))

    # New constraint + indexes
    op.create_unique_constraint(
        "uq_module_schema_mapping",
        "project_field_mapping",
        ["source_module_id", "datahash_schema_id"],
    )
    op.create_index("ix_project_field_mapping_module_id", "project_field_mapping", ["source_module_id"])
    op.create_index("ix_project_field_mapping_schema_id", "project_field_mapping", ["datahash_schema_id"])

    # ── project_integration ──────────────────────────────────────────────────

    # Drop old constraint, index, and sub_destination_slug FK
    op.drop_constraint("uq_integration", "project_integration", type_="unique")
    op.drop_constraint("project_integration_sub_destination_slug_fkey", "project_integration", type_="foreignkey")
    op.drop_index("ix_project_integration_source_module_id", table_name="project_integration")
    op.drop_index("ix_project_integration_destination_conn_id", table_name="project_integration")
    op.drop_column("project_integration", "sub_destination_slug")

    # Add destination_id
    op.add_column("project_integration", sa.Column("destination_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_project_integration_destination_id",
        "project_integration",
        "destination",
        ["destination_id"],
        ["id"],
    )
    op.alter_column("project_integration", "destination_id", nullable=False)

    # Add is_deleted
    op.add_column("project_integration", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"))

    # New constraint + indexes
    op.create_unique_constraint(
        "uq_integration",
        "project_integration",
        ["source_module_id", "destination_conn_id", "destination_id"],
    )
    op.create_index("ix_project_integration_module_id", "project_integration", ["source_module_id"])
    op.create_index("ix_project_integration_dest_conn_id", "project_integration", ["destination_conn_id"])


def downgrade() -> None:
    # ── project_integration ──────────────────────────────────────────────────
    op.drop_index("ix_project_integration_dest_conn_id", table_name="project_integration")
    op.drop_index("ix_project_integration_module_id", table_name="project_integration")
    op.drop_constraint("uq_integration", "project_integration", type_="unique")
    op.drop_column("project_integration", "is_deleted")
    op.drop_constraint("fk_project_integration_destination_id", "project_integration", type_="foreignkey")
    op.drop_column("project_integration", "destination_id")
    op.add_column(
        "project_integration", sa.Column("sub_destination_slug", sa.Text(), nullable=False, server_default="")
    )
    op.alter_column("project_integration", "sub_destination_slug", server_default=None)
    op.create_foreign_key(
        "project_integration_sub_destination_slug_fkey",
        "project_integration",
        "connector",
        ["sub_destination_slug"],
        ["connector_slug"],
    )
    op.create_unique_constraint(
        "uq_integration", "project_integration", ["source_module_id", "destination_conn_id", "sub_destination_slug"]
    )
    op.create_index("ix_project_integration_destination_conn_id", "project_integration", ["destination_conn_id"])
    op.create_index("ix_project_integration_source_module_id", "project_integration", ["source_module_id"])

    # ── project_field_mapping ────────────────────────────────────────────────
    op.drop_index("ix_project_field_mapping_schema_id", table_name="project_field_mapping")
    op.drop_index("ix_project_field_mapping_module_id", table_name="project_field_mapping")
    op.drop_constraint("uq_module_schema_mapping", "project_field_mapping", type_="unique")
    op.drop_column("project_field_mapping", "confidence")
    op.add_column("project_field_mapping", sa.Column("confidence", sa.Text(), nullable=True))
    op.drop_column("project_field_mapping", "is_deleted")
    op.drop_column("project_field_mapping", "is_tombstone")
    op.drop_constraint("fk_project_field_mapping_schema_id", "project_field_mapping", type_="foreignkey")
    op.drop_column("project_field_mapping", "datahash_schema_id")
    op.add_column("project_field_mapping", sa.Column("canonical_key", sa.Text(), nullable=False, server_default=""))
    op.alter_column("project_field_mapping", "canonical_key", server_default=None)
    op.create_foreign_key(
        "project_field_mapping_canonical_key_fkey",
        "project_field_mapping",
        "datahash_schema",
        ["canonical_key"],
        ["canonical_key"],
    )
    op.create_unique_constraint(
        "uq_module_canonical_key", "project_field_mapping", ["source_module_id", "canonical_key"]
    )
    op.create_index("ix_project_field_mapping_source_module_id", "project_field_mapping", ["source_module_id"])
