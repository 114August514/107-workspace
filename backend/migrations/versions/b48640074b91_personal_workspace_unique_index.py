"""一个用户只能有一个 Personal Workspace。

先查后写挡不住并发：新用户首屏的几个请求会同时发现「还没有」然后各建一个。
协作空间可以有多个，所以是**部分**唯一索引，只约束 kind=personal。
SQLite 和 PostgreSQL 都支持部分索引。

Revision ID: b48640074b91
Revises: 820b10c622f1
Create Date: 2026-07-27 01:40:17.672214
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b48640074b91"
down_revision: str | None = "820b10c622f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.create_index(
            "uq_personal_workspace",
            ["owner_id"],
            unique=True,
            sqlite_where=sa.text("kind = 'personal'"),
            postgresql_where=sa.text("kind = 'personal'"),
        )


def downgrade() -> None:
    with op.batch_alter_table("workspaces", schema=None) as batch_op:
        batch_op.drop_index(
            "uq_personal_workspace",
            sqlite_where=sa.text("kind = 'personal'"),
            postgresql_where=sa.text("kind = 'personal'"),
        )
