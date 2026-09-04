"""variables 表增加 updated_at 列。

Settings 页面要展示「最近更新」，而 variables 表此前没有时间列
（secrets 表一开始就有）。SQLite 不允许用 ALTER 加「非常量默认值的
NOT NULL 列」，沿用先可空 -> 回填 -> 再收紧的既有套路。

Revision ID: b3d8e2a64c19
Revises: e46a1b2c3d4e
Create Date: 2026-09-04 01:40:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3d8e2a64c19"
down_revision: str | None = "e46a1b2c3d4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("variables", schema=None) as batch_op:
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE variables SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
    )

    with op.batch_alter_table("variables", schema=None) as batch_op:
        batch_op.alter_column(
            "updated_at", existing_type=sa.DateTime(timezone=True), nullable=False
        )


def downgrade() -> None:
    with op.batch_alter_table("variables", schema=None) as batch_op:
        batch_op.drop_column("updated_at")
