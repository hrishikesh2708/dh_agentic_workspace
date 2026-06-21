"""Update project table: add is_deleted, rename user_id index.

Revision ID: n9c0d1e2f3a4
Revises: m8b9c0d1e2f3
Create Date: 2026-06-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n9c0d1e2f3a4"
down_revision: Union[str, Sequence[str], None] = "m8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("project", "is_deleted")
