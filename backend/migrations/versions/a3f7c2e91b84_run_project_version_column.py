"""runs 表增加 project_version_id 和 project_version_label 列。

Run History 需要展示每个 Run 对应的 Project 版本（design L192），但
project_version_id 只存在于 run_snapshots 的 JSON 里，无法在列表查询中
直接获取。冗余到 runs 表的列，模式同 compute_plan_id。

project_version_label 也一并冗余：label = f"v{sequence}" 是计算属性
（models.py），sequence 受 UniqueConstraint("project_id", "sequence")
约束且版本不可变（GR-201），所以冗余 label 不会漂移，与 GR-205 一致。
先例：fork_relations.source_version_label 已采用同样的 label 冗余。

已有数据从快照 + project_versions 表回填。**不能直接加 NOT NULL 列**：
表里已经有行，加了就会失败。走「先可空 -> 回填 -> 再收紧」三步。

Revision ID: a3f7c2e91b84
Revises: b48640074b91
Create Date: 2026-08-13 00:00:00.000000
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3f7c2e91b84"
down_revision: str | None = "b48640074b91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("project_version_id", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("project_version_label", sa.String(length=32), nullable=True))

    _backfill_from_snapshots()

    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.alter_column("project_version_id", existing_type=sa.String(length=40), nullable=False)
        batch_op.alter_column("project_version_label", existing_type=sa.String(length=32), nullable=False)
        batch_op.create_index("ix_runs_project_version_id", ["project_version_id"], unique=False)


def _backfill_from_snapshots() -> None:
    """从每个 Run 的快照 JSON 取出 project_version_id，再查 project_versions
    拿到 sequence，在 Python 中按 f"v{sequence}" 生成 label。

    label 是计算属性 f"v{self.sequence}"，project_versions 表没有 label 列。
    """
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT r.id, s.payload FROM runs r JOIN run_snapshots s ON s.id = r.snapshot_id")
    ).fetchall()

    # 批量查 sequence，避免逐行查询
    version_ids = set()
    for _run_id, payload in rows:
        data = json.loads(payload) if isinstance(payload, str) else payload
        vid = data.get("project_version_id", "")
        if vid:
            version_ids.add(vid)

    seq_map: dict[str, int] = {}
    if version_ids:
        placeholders = ", ".join(f":v{i}" for i in range(len(version_ids)))
        params = {f"v{i}": vid for i, vid in enumerate(version_ids)}
        result = connection.execute(
            sa.text(f"SELECT id, sequence FROM project_versions WHERE id IN ({placeholders})"),
            params,
        )
        seq_map = {row[0]: row[1] for row in result}

    for run_id, payload in rows:
        data = json.loads(payload) if isinstance(payload, str) else payload
        version_id = data.get("project_version_id", "")
        sequence = seq_map.get(version_id, 0)
        label = f"v{sequence}"
        connection.execute(
            sa.text(
                "UPDATE runs SET project_version_id = :vid, project_version_label = :label WHERE id = :id"
            ),
            {"vid": version_id, "label": label, "id": run_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_index("ix_runs_project_version_id")
        batch_op.drop_column("project_version_label")
        batch_op.drop_column("project_version_id")
