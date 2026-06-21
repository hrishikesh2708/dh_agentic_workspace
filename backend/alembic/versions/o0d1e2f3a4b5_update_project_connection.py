"""Update project_connection table: replace connector_slug with connection_type/source_id/destination_id.

Revision ID: o0d1e2f3a4b5
Revises: n9c0d1e2f3a4
Create Date: 2026-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "n9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old unique constraint and connector_slug FK constraint
    op.drop_constraint("uq_project_connector", "project_connection", type_="unique")
    op.drop_constraint("project_connection_connector_slug_fkey", "project_connection", type_="foreignkey")

    # Drop old columns
    op.drop_column("project_connection", "connector_slug")
    op.drop_column("project_connection", "connected_at")
    op.drop_column("project_connection", "connected_by")

    # Add new columns
    op.add_column(
        "project_connection", sa.Column("connection_type", sa.Text(), nullable=False, server_default="source")
    )
    op.add_column("project_connection", sa.Column("source_id", sa.Integer(), nullable=True))
    op.add_column("project_connection", sa.Column("destination_id", sa.Integer(), nullable=True))
    op.add_column("project_connection", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column(
        "project_connection",
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # Remove server_default now that existing rows are backfilled
    op.alter_column("project_connection", "connection_type", server_default=None)

    # Add FK constraints
    op.create_foreign_key(
        "fk_project_connection_source_id",
        "project_connection",
        "source",
        ["source_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_project_connection_destination_id",
        "project_connection",
        "destination",
        ["destination_id"],
        ["id"],
    )

    # Add lookup indexes
    op.create_index("ix_project_connection_source_id", "project_connection", ["source_id"])
    op.create_index("ix_project_connection_destination_id", "project_connection", ["destination_id"])

    # CHECK: exactly one of source_id / destination_id must be non-null
    op.create_check_constraint(
        "ck_project_connection_xor_source_destination",
        "project_connection",
        "(source_id IS NOT NULL AND destination_id IS NULL) OR (source_id IS NULL AND destination_id IS NOT NULL)",
    )

    # Partial unique indexes (NULL != NULL in Postgres, so standard unique won't work)
    op.execute(
        "CREATE UNIQUE INDEX uq_project_source_conn "
        "ON project_connection(project_id, source_id) "
        "WHERE source_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_project_destination_conn "
        "ON project_connection(project_id, destination_id) "
        "WHERE destination_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_project_destination_conn")
    op.execute("DROP INDEX IF EXISTS uq_project_source_conn")
    op.drop_constraint("ck_project_connection_xor_source_destination", "project_connection", type_="check")
    op.drop_index("ix_project_connection_destination_id", table_name="project_connection")
    op.drop_index("ix_project_connection_source_id", table_name="project_connection")
    op.drop_constraint("fk_project_connection_destination_id", "project_connection", type_="foreignkey")
    op.drop_constraint("fk_project_connection_source_id", "project_connection", type_="foreignkey")
    op.drop_column("project_connection", "created_at")
    op.drop_column("project_connection", "is_deleted")
    op.drop_column("project_connection", "destination_id")
    op.drop_column("project_connection", "source_id")
    op.drop_column("project_connection", "connection_type")
    op.add_column("project_connection", sa.Column("connector_slug", sa.Text(), nullable=False))
    op.add_column(
        "project_connection",
        sa.Column("connected_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.add_column("project_connection", sa.Column("connected_by", sa.Text(), nullable=True))
    op.create_foreign_key(
        "project_connection_connector_slug_fkey",
        "project_connection",
        "connector",
        ["connector_slug"],
        ["connector_slug"],
    )
    op.create_unique_constraint("uq_project_connector", "project_connection", ["project_id", "connector_slug"])
