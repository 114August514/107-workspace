"""建立 Fork 来源记录表。

source_* 里的名字是 Fork 那一刻抄下来的快照，不做外键——
源 Project 删掉之后「这个项目从哪儿来的」仍然要读得通。
project_id 唯一：一个 Project 只可能 Fork 自一个地方。

Revision ID: 9ac12d5a3764
Revises: de1e5e1dd6ab
Create Date: 2026-07-27 00:19:47.926564
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9ac12d5a3764"
down_revision: str | None = "de1e5e1dd6ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fork_relations",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("project_id", sa.String(length=40), nullable=False),
        sa.Column("source_project_id", sa.String(length=40), nullable=False),
        sa.Column("source_version_id", sa.String(length=40), nullable=False),
        sa.Column("source_workspace_id", sa.String(length=40), nullable=False),
        sa.Column("source_project_name", sa.String(length=255), nullable=False),
        sa.Column("source_version_label", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
    )
    with op.batch_alter_table("fork_relations", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_fork_relations_source_project_id"), ["source_project_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("fork_relations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_fork_relations_source_project_id"))

    op.drop_table("fork_relations")
