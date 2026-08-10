"""Project Version clean cutover 到完整 Git commit OID。

旧 project_files / project_version_files 只描述 blob manifest，无法证明真实 Git
repository 与 commit identity。本迁移明确删除可重建的开发版本数据，不做 fallback；
部署前若发现必须保留的数据，应停止升级并另行设计一次性导入。

Revision ID: a1f0e2d3c4b5
Revises: b48640074b91
Create Date: 2026-08-10 11:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1f0e2d3c4b5"
down_revision: str | None = "b48640074b91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("project_version_files")
    op.drop_table("project_files")

    # 旧版本没有可验证的 Git commit identity，不能伪造 OID 或保留不可读取的记录。
    op.execute(sa.text("DELETE FROM project_versions"))
    with op.batch_alter_table("project_versions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("commit_oid", sa.String(length=64), nullable=False))
        batch_op.add_column(sa.Column("file_count", sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column("total_size", sa.Integer(), nullable=False))
        batch_op.create_check_constraint(
            "ck_version_commit_oid_length", "length(commit_oid) IN (40, 64)"
        )
        batch_op.create_unique_constraint("uq_version_commit_oid", ["project_id", "commit_oid"])


def downgrade() -> None:
    # downgrade 恢复旧 schema，不可能从 commit OID 无损重建已删除的旧 blob manifest。
    with op.batch_alter_table("project_versions", schema=None) as batch_op:
        batch_op.drop_constraint("uq_version_commit_oid", type_="unique")
        batch_op.drop_constraint("ck_version_commit_oid_length", type_="check")
        batch_op.drop_column("total_size")
        batch_op.drop_column("file_count")
        batch_op.drop_column("commit_oid")

    op.create_table(
        "project_files",
        sa.Column("project_id", sa.String(length=40), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("project_id", "path"),
    )
    op.create_table(
        "project_version_files",
        sa.Column("version_id", sa.String(length=40), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["project_versions.id"]),
        sa.PrimaryKeyConstraint("version_id", "path"),
    )
