"""Drop unused thread table.

Revision ID: h3c4d5e6f7a8
Revises: g2b3c4d5e6f7
Create Date: 2026-06-16

Thread model was removed — the table has no references anywhere in the codebase.
"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "h3c4d5e6f7a8"  # pragma: allowlist secret
down_revision: str = "g2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop the unused thread table."""
    op.drop_table("thread")


def downgrade() -> None:
    """Recreate the thread table."""
    op.create_table(
        "thread",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
