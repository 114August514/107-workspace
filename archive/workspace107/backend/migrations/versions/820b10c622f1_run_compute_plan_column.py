"""runs 表增加 compute_plan_id 列。

并发额度的口径是「Workspace × 算力方案」（GR-002a），数未结束 Run 时
必须能按方案过滤。方案存在 run_snapshots 的 JSON 里，没法索引也没法
跨库稳定地查，所以冗余成一列——方案在快照创建时固定、之后不再变。

已有数据从快照里回填。**不能直接加 NOT NULL 列**：表里已经有行，
加了就会失败。所以走「先可空 -> 回填 -> 再收紧」三步。

Revision ID: 820b10c622f1
Revises: 9ac12d5a3764
Create Date: 2026-07-27 01:25:35.875273
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "820b10c622f1"
down_revision: str | None = "9ac12d5a3764"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("compute_plan_id", sa.String(length=40), nullable=True))

    _backfill_from_snapshots()

    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.alter_column("compute_plan_id", existing_type=sa.String(length=40), nullable=False)
        batch_op.create_index("ix_runs_compute_plan_id", ["compute_plan_id"], unique=False)


def _backfill_from_snapshots() -> None:
    """从每个 Run 的快照 JSON 里取出算力方案填进新列。

    用 Python 解析而不是数据库的 JSON 函数：SQLite 和 PostgreSQL 的
    JSON 语法不一样，走 Python 两边都能跑。Run 数量在这个阶段很小，
    一次性读进来没有问题。
    """
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT r.id, s.payload FROM runs r JOIN run_snapshots s ON s.id = r.snapshot_id")
    ).fetchall()

    for run_id, payload in rows:
        # SQLite 里 JSON 列读出来是字符串，PostgreSQL 里已经是 dict
        data = json.loads(payload) if isinstance(payload, str) else payload
        plan_id = (data.get("compute") or {}).get("plan_id", "")
        connection.execute(
            sa.text("UPDATE runs SET compute_plan_id = :plan WHERE id = :id"),
            {"plan": plan_id, "id": run_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_index("ix_runs_compute_plan_id")
        batch_op.drop_column("compute_plan_id")
