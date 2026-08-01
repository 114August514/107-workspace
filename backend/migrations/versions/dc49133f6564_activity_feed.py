"""建立活动流表。

活动是历史事实，只增不改。actor_name / target_name 是写入时抄下来的快照，
所以不做外键——对象改名或删除之后活动仍然要读得通。

Revision ID: dc49133f6564
Revises: 7341e47b9d36
Create Date: 2026-07-26 22:02:57.142443
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "dc49133f6564"
down_revision: str | None = "7341e47b9d36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "activities",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("workspace_id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=40), nullable=True),
        sa.Column("actor_id", sa.String(length=40), nullable=False),
        sa.Column("actor_name", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=40), nullable=False),
        sa.Column("target_name", sa.String(length=255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.create_index(
            "ix_activities_project_created", ["project_id", "created_at"], unique=False
        )
        batch_op.create_index(
            "ix_activities_workspace_created", ["workspace_id", "created_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("activities", schema=None) as batch_op:
        batch_op.drop_index("ix_activities_workspace_created")
        batch_op.drop_index("ix_activities_project_created")

    op.drop_table("activities")
