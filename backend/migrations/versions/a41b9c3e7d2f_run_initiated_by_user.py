"""Converge Run semantics on Initiated By User and exact Environment Version.

Issue #41:

- ``runs.created_by`` 重命名为 ``initiated_by_user_id``。原列记录的本就是
  发起 Run 的 User，这里只是把名字对齐 GR-307 的统一身份字段，
  数据语义不变（backfill = rename 本身）。
- ``run_snapshots.payload`` 里的 identity key 同步从 ``created_by`` 改名为
  ``initiated_by_user_id``。Snapshot 行是不可变的执行事实，这里只对齐
  key 名，value 原样保留——否则升级后留下的 Snapshot 是新代码
  ``from_payload`` 无法读取的半迁移状态。
- ``run_configurations.environment_version_id`` 收紧为 NOT NULL。运行方案必须
  精确引用一个 Environment Version，运行时不再有「继承 Project / Workspace
  默认环境」的回退链。历史上为 NULL 的行直接删除——产品尚未投入使用，
  本地库重建即可（显式策略，migration 测试钉住）。
- ``idempotency_keys`` 主键从 ``(workspace_id, key)`` 改为
  ``(initiated_by_user_id, key)``：幂等作用域从 Workspace 收敛到发起 User。
  旧登记无法从 workspace 推导出发起人，直接丢弃（产品未上线）。

Revision ID: a41b9c3e7d2f
Revises: f36a1b2c3d4e
Create Date: 2026-08-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a41b9c3e7d2f"
down_revision: str | None = "f36a1b2c3d4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rename_snapshot_identity_key(old_key: str, new_key: str) -> None:
    """把每个 RunSnapshot payload 里的 identity key 改名，value 不动。

    用 SQLAlchemy 的 JSON 类型做读写，让方言自己处理序列化——SQLite 存
    TEXT、Postgres 用原生 json，同一个表达式两边都能跑。key 不存在的行
    （空 payload、损坏行或已迁移过的行）原样跳过。
    """
    snapshots = sa.table(
        "run_snapshots",
        sa.column("id", sa.String),
        sa.column("payload", sa.JSON),
    )
    connection = op.get_bind()
    for row in connection.execute(snapshots.select()).fetchall():
        payload = dict(row.payload) if row.payload else {}
        if old_key not in payload:
            continue
        payload[new_key] = payload.pop(old_key)
        connection.execute(
            snapshots.update().where(snapshots.c.id == row.id).values(payload=payload)
        )


def upgrade() -> None:
    op.drop_index("ix_runs_created_by", table_name="runs")
    with op.batch_alter_table("runs") as batch:
        batch.alter_column(
            "created_by", new_column_name="initiated_by_user_id", existing_type=sa.String(40)
        )
    op.create_index("ix_runs_initiated_by_user_id", "runs", ["initiated_by_user_id"])

    _rename_snapshot_identity_key("created_by", "initiated_by_user_id")

    op.get_bind().execute(
        sa.text("DELETE FROM run_configurations WHERE environment_version_id IS NULL")
    )
    with op.batch_alter_table("run_configurations") as batch:
        batch.alter_column("environment_version_id", existing_type=sa.String(40), nullable=False)

    op.drop_table("idempotency_keys")
    op.create_table(
        "idempotency_keys",
        sa.Column("initiated_by_user_id", sa.String(length=40), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("endpoint", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("initiated_by_user_id", "key"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.create_table(
        "idempotency_keys",
        sa.Column("workspace_id", sa.String(length=40), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("endpoint", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("workspace_id", "key"),
    )

    with op.batch_alter_table("run_configurations") as batch:
        batch.alter_column("environment_version_id", existing_type=sa.String(40), nullable=True)

    op.drop_index("ix_runs_initiated_by_user_id", table_name="runs")
    with op.batch_alter_table("runs") as batch:
        batch.alter_column(
            "initiated_by_user_id", new_column_name="created_by", existing_type=sa.String(40)
        )
    op.create_index("ix_runs_created_by", "runs", ["created_by"])

    _rename_snapshot_identity_key("initiated_by_user_id", "created_by")
