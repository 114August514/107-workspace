"""Add per-user notification preferences.

Absent rows use the product default (enabled). Mandatory notification categories are
validated by the application and are never disabled.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f50a9b7c6d5e"
down_revision: str | None = "e46a1b2c3d4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("notification_type", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "notification_type"),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
