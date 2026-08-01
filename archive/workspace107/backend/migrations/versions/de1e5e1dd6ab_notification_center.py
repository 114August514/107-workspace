"""建立通知表。

通知按收件人查，不按 Workspace 查——被移除的成员已经看不到那个空间，
但「你被移除了」这条通知必须还能读到。所以 recipient_id 上没有外键约束到
memberships，索引也是 recipient_id + created_at。

Revision ID: de1e5e1dd6ab
Revises: dc49133f6564
Create Date: 2026-07-26 23:56:10.806323
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "de1e5e1dd6ab"
down_revision: str | None = "dc49133f6564"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("recipient_id", sa.String(length=40), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("workspace_id", sa.String(length=40), nullable=True),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.String(length=40), nullable=True),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.create_index(
            "ix_notifications_recipient_created", ["recipient_id", "created_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.drop_index("ix_notifications_recipient_created")

    op.drop_table("notifications")
