"""Update oauth_pending: replace connector_slug with connection_type/source_id/destination_id, add FK on session_id.

Revision ID: s4b5c6d7e8f9
Revises: r3a4b5c6d7e8
Create Date: 2026-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "r3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old index and connector_slug column
    op.drop_index("ix_oauth_pending_connector_slug", table_name="oauth_pending")
    op.drop_index("ix_oauth_pending_project_id", table_name="oauth_pending")
    op.drop_column("oauth_pending", "connector_slug")

    # Add FK on session_id (was a plain varchar before)
    op.create_foreign_key(
        "fk_oauth_pending_session_id",
        "oauth_pending",
        "session",
        ["session_id"],
        ["id"],
    )

    # Add new columns
    op.add_column("oauth_pending", sa.Column("connection_type", sa.Text(), nullable=True))
    op.add_column("oauth_pending", sa.Column("source_id", sa.Integer(), nullable=True))
    op.add_column("oauth_pending", sa.Column("destination_id", sa.Integer(), nullable=True))

    op.create_foreign_key(
        "fk_oauth_pending_source_id",
        "oauth_pending",
        "source",
        ["source_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_oauth_pending_destination_id",
        "oauth_pending",
        "destination",
        ["destination_id"],
        ["id"],
    )

    # Backfill connection_type before making it non-nullable
    # (existing rows will need manual backfill in practice)
    op.execute("UPDATE oauth_pending SET connection_type = 'source' WHERE connection_type IS NULL")
    op.alter_column("oauth_pending", "connection_type", nullable=False)

    # CHECK: exactly one of source_id / destination_id must be non-null
    op.create_check_constraint(
        "ck_oauth_pending_xor_source_destination",
        "oauth_pending",
        "(source_id IS NOT NULL AND destination_id IS NULL) OR (source_id IS NULL AND destination_id IS NOT NULL)",
    )

    # Recreate indexes with canonical names
    op.create_index("ix_oauth_pending_project_id", "oauth_pending", ["project_id"])
    op.create_index("ix_oauth_pending_source_id", "oauth_pending", ["source_id"])
    op.create_index("ix_oauth_pending_destination_id", "oauth_pending", ["destination_id"])


def downgrade() -> None:
    op.drop_index("ix_oauth_pending_destination_id", table_name="oauth_pending")
    op.drop_index("ix_oauth_pending_source_id", table_name="oauth_pending")
    op.drop_index("ix_oauth_pending_project_id", table_name="oauth_pending")
    op.drop_constraint("ck_oauth_pending_xor_source_destination", "oauth_pending", type_="check")
    op.drop_constraint("fk_oauth_pending_destination_id", "oauth_pending", type_="foreignkey")
    op.drop_constraint("fk_oauth_pending_source_id", "oauth_pending", type_="foreignkey")
    op.drop_column("oauth_pending", "destination_id")
    op.drop_column("oauth_pending", "source_id")
    op.drop_column("oauth_pending", "connection_type")
    op.drop_constraint("fk_oauth_pending_session_id", "oauth_pending", type_="foreignkey")
    op.add_column("oauth_pending", sa.Column("connector_slug", sa.Text(), nullable=False, server_default=""))
    op.alter_column("oauth_pending", "connector_slug", server_default=None)
    op.create_index("ix_oauth_pending_connector_slug", "oauth_pending", ["connector_slug"])
    op.create_index("ix_oauth_pending_project_id", "oauth_pending", ["project_id"])
