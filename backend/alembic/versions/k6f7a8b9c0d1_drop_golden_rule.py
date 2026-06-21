"""Drop golden_rule table.

Revision ID: k6f7a8b9c0d1
Revises: j5e6f7a8b9c0
Create Date: 2026-06-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "j5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_golden_rule_source_pattern", table_name="golden_rule")
    op.drop_index("ix_golden_rule_destination_type", table_name="golden_rule")
    op.drop_table("golden_rule")


def downgrade() -> None:
    op.create_table(
        "golden_rule",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_pattern", sa.String(255), nullable=False),
        sa.Column("destination_field", sa.String(255), nullable=False),
        sa.Column("destination_type", sa.String(255), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_golden_rule_source_pattern", "golden_rule", ["source_pattern"])
    op.create_index("ix_golden_rule_destination_type", "golden_rule", ["destination_type"])
