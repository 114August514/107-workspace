"""建立 Shared Resource 三张表。

设计稿 §3.1.3、§2.6 把 Shared Resource 定义为独立于 Project 存在、
可版本化、可被多个 Project 通过 Input Binding 引用的内容资源。
当前 ``InputBinding`` 和 ``InputSourceType`` 已预留
``shared_resource_version`` 枚举值和 ``SharedResourceVersion -> InputBinding -> Run``
的引用链路，但 Shared Resource 本身的表不存在，Input Binding 实际上
只能走 Artifact 一条路——而 Artifact 是 Run 的输出，不是一手数据集。

本次三张表让 M3 Reusable Run 的「创建 Platform Shared Resource -> 上传文件 ->
在 Input Binding 中引用 -> Run 读取到输入」闭环得以成立。

- ``shared_resources``：可变资源对象，``owner_workspace_id`` 为 NULL 表示
  Platform 持有。Core 子集只分 Platform（全平台可见）和 Workspace（成员可见）
  两层；跨 Workspace Asset Grant 在 M4 单独 Issue。
- ``shared_resource_versions``：不可变版本（GR-201），按 ``sequence`` 自增展示
  v1、v2……。和 ``project_versions`` 同模式：先插版本行，再插文件行。
- ``shared_resource_version_files``：版本内容按 ``(path, size, content_hash)``
  三元组固化。文件正文存在存储层按内容寻址的 blob store，与 Project Version
  共用同一个 blob 池，所以本表不需要存储路径列。

新增能力（``SHARED_RESOURCE_VIEW / MANAGE / VERSION_CREATE``）和活动 /
通知枚举值的扩展在 domain 层同步进行，不依赖本迁移。

Revision ID: fdb5011fe3b2
Revises: b48640074b91
Create Date: 2026-08-06 19:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fdb5011fe3b2"
down_revision: str | None = "b48640074b91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shared_resources",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner_workspace_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("shared_resources", schema=None) as batch_op:
        batch_op.create_index(
            "ix_shared_resources_owner_workspace_id",
            ["owner_workspace_id"],
            unique=False,
        )

    op.create_table(
        "shared_resource_versions",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("shared_resource_id", sa.String(length=40), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["shared_resource_id"],
            ["shared_resources.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "shared_resource_id", "sequence", name="uq_shared_resource_version_seq"
        ),
    )
    with op.batch_alter_table("shared_resource_versions", schema=None) as batch_op:
        batch_op.create_index(
            "ix_shared_resource_versions_shared_resource_id",
            ["shared_resource_id"],
            unique=False,
        )

    op.create_table(
        "shared_resource_version_files",
        sa.Column("version_id", sa.String(length=40), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["shared_resource_versions.id"],
        ),
        sa.PrimaryKeyConstraint("version_id", "path"),
    )


def downgrade() -> None:
    op.drop_table("shared_resource_version_files")
    with op.batch_alter_table("shared_resource_versions", schema=None) as batch_op:
        batch_op.drop_index(
            "ix_shared_resource_versions_shared_resource_id",
        )
    op.drop_table("shared_resource_versions")
    with op.batch_alter_table("shared_resources", schema=None) as batch_op:
        batch_op.drop_index(
            "ix_shared_resources_owner_workspace_id",
        )
    op.drop_table("shared_resources")
