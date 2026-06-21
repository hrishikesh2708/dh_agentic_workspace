"""Update project_source_module: replace module_type/module_identifier with source_object, add signal_type/is_deleted.

Revision ID: p1e2f3a4b5c6
Revises: o0d1e2f3a4b5
Create Date: 2026-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "o0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old unique constraint and index
    op.drop_constraint("uq_source_module", "project_source_module", type_="unique")
    op.drop_index("ix_project_source_module_project_connection_id", table_name="project_source_module")

    # Drop removed columns
    op.drop_column("project_source_module", "module_type")
    op.drop_column("project_source_module", "module_identifier")

    # Add new columns
    # source_object: backfill with empty string, then make non-nullable
    op.add_column("project_source_module", sa.Column("source_object", sa.Text(), nullable=True))
    op.execute("UPDATE project_source_module SET source_object = '' WHERE source_object IS NULL")
    op.alter_column("project_source_module", "source_object", nullable=False)

    op.add_column("project_source_module", sa.Column("signal_type", sa.Text(), nullable=True))
    op.add_column(
        "project_source_module", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false")
    )

    # New unique constraint and index with canonical names
    op.create_unique_constraint(
        "uq_source_module_object",
        "project_source_module",
        ["project_connection_id", "source_object"],
    )
    op.create_index("ix_source_module_conn_id", "project_source_module", ["project_connection_id"])


def downgrade() -> None:
    op.drop_index("ix_source_module_conn_id", table_name="project_source_module")
    op.drop_constraint("uq_source_module_object", "project_source_module", type_="unique")
    op.drop_column("project_source_module", "is_deleted")
    op.drop_column("project_source_module", "signal_type")
    op.drop_column("project_source_module", "source_object")
    op.add_column(
        "project_source_module", sa.Column("module_identifier", sa.Text(), nullable=False, server_default="")
    )
    op.add_column("project_source_module", sa.Column("module_type", sa.Text(), nullable=False, server_default="leads"))
    op.alter_column("project_source_module", "module_identifier", server_default=None)
    op.alter_column("project_source_module", "module_type", server_default=None)
    op.create_unique_constraint(
        "uq_source_module", "project_source_module", ["project_connection_id", "module_identifier"]
    )
    op.create_index(
        "ix_project_source_module_project_connection_id", "project_source_module", ["project_connection_id"]
    )
