"""Update user and session schema.

Changes:
- user: add is_deleted (bool, default false), updated_at (timestamptz)
- session: make project_id non-nullable, add status, last_active_at,
           is_deleted, updated_at; drop username column; add user_id index

Revision ID: i4d5e6f7a8b9
Revises: h3c4d5e6f7a8
Create Date: 2026-06-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "h3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── user table ──────────────────────────────────────────────────────────
    op.add_column("user", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column(
        "user", sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()"))
    )

    # ── session table ────────────────────────────────────────────────────────

    # 1. Fill any NULL project_id rows before enforcing NOT NULL.
    #    In practice there should be none in dev; this prevents migration failure
    #    if old test data exists.
    op.execute(
        """
        DELETE FROM session
        WHERE project_id IS NULL
        """
    )

    # 2. Make project_id non-nullable
    op.alter_column("session", "project_id", existing_type=sa.UUID(), nullable=False)

    # 3. Add new columns
    op.add_column("session", sa.Column("status", sa.String(), nullable=False, server_default="active"))
    op.add_column(
        "session",
        sa.Column("last_active_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.add_column("session", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column(
        "session",
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 4. Drop old username column (replaced by user relationship)
    op.drop_column("session", "username")

    # 5. Add index on user_id (project_id index already exists)
    op.create_index("ix_session_user_id", "session", ["user_id"])


def downgrade() -> None:
    # session
    op.drop_index("ix_session_user_id", table_name="session")
    op.drop_column("session", "updated_at")
    op.drop_column("session", "is_deleted")
    op.drop_column("session", "last_active_at")
    op.drop_column("session", "status")
    op.add_column("session", sa.Column("username", sa.String(), nullable=True))
    op.alter_column("session", "project_id", existing_type=sa.UUID(), nullable=True)

    # user
    op.drop_column("user", "updated_at")
    op.drop_column("user", "is_deleted")
