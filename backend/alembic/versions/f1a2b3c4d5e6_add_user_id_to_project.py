"""Add user_id to project table.

Revision ID: f1a2b3c4d5e6
Revises: e8f9a0b1c2d3
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"  # pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add user ownership to projects."""
    op.add_column("project", sa.Column("user_id", sa.Integer(), nullable=True))
    # Existing rows cannot be attributed to a user; drop before enforcing NOT NULL.
    op.execute("DELETE FROM project")
    op.alter_column("project", "user_id", nullable=False)
    op.create_index(op.f("ix_project_user_id"), "project", ["user_id"], unique=False)
    op.create_foreign_key(
        "fk_project_user_id",
        "project",
        "user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint("uq_project_user_name", "project", ["user_id", "name"])


def downgrade() -> None:
    """Remove user ownership from projects."""
    op.drop_constraint("uq_project_user_name", "project", type_="unique")
    op.drop_constraint("fk_project_user_id", "project", type_="foreignkey")
    op.drop_index(op.f("ix_project_user_id"), table_name="project")
    op.drop_column("project", "user_id")
