"""Add oauth_pending table and session.project_id.

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2025-06-15 00:00:00.000000

Changes:
- Creates ``oauth_pending`` table for transient PKCE state during OAuth flows.
- Adds nullable ``project_id`` FK column to ``session`` table so each copilot
  chat session is scoped to a specific project workspace.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "g2b3c4d5e6f7"  # pragma: allowlist secret
down_revision = "f1a2b3c4d5e6"  # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create oauth_pending and add session.project_id."""
    # ------------------------------------------------------------------
    # 1. oauth_pending — transient PKCE state during OAuth handshakes
    # ------------------------------------------------------------------
    op.create_table(
        "oauth_pending",
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("connector_slug", sa.String(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("pkce_verifier", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("state"),
    )
    op.create_index("ix_oauth_pending_connector_slug", "oauth_pending", ["connector_slug"])
    op.create_index("ix_oauth_pending_project_id", "oauth_pending", ["project_id"])

    # ------------------------------------------------------------------
    # 2. session.project_id — scope copilot sessions to a project
    # ------------------------------------------------------------------
    op.add_column(
        "session",
        sa.Column("project_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_session_project_id",
        "session",
        "project",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_session_project_id", "session", ["project_id"])


def downgrade() -> None:
    """Drop oauth_pending and session.project_id."""
    op.drop_index("ix_session_project_id", table_name="session")
    op.drop_constraint("fk_session_project_id", "session", type_="foreignkey")
    op.drop_column("session", "project_id")

    op.drop_index("ix_oauth_pending_project_id", table_name="oauth_pending")
    op.drop_index("ix_oauth_pending_connector_slug", table_name="oauth_pending")
    op.drop_table("oauth_pending")
