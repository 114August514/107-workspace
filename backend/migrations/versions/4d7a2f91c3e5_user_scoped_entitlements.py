"""Scope Resource Entitlement to User instead of Workspace.

Issue #38: entitlement 的业务主键从 ``workspace_id`` 换成 ``user_id``。
没有数据回填——产品尚未投入使用，旧行没有保留价值，本地库直接重建。
downgrade 同样不恢复数据，只还原表结构。

Revision ID: 4d7a2f91c3e5
Revises: e35a1d7c9b20
Create Date: 2026-08-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4d7a2f91c3e5"
down_revision: str | None = "e35a1d7c9b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ID = sa.String(length=40)


def upgrade() -> None:
    with op.batch_alter_table("resource_entitlements", schema=None) as batch_op:
        batch_op.drop_constraint("uq_entitlement", type_="unique")
        batch_op.drop_index(batch_op.f("ix_resource_entitlements_workspace_id"))
        batch_op.drop_column("workspace_id")
        batch_op.add_column(sa.Column("user_id", _ID, nullable=False))
        batch_op.create_foreign_key(
            batch_op.f("fk_resource_entitlements_user_id_users"), "users", ["user_id"], ["id"]
        )
        batch_op.create_index(
            batch_op.f("ix_resource_entitlements_user_id"), ["user_id"], unique=False
        )
        batch_op.create_unique_constraint("uq_entitlement", ["user_id", "compute_plan_id"])


def downgrade() -> None:
    with op.batch_alter_table("resource_entitlements", schema=None) as batch_op:
        batch_op.drop_constraint("uq_entitlement", type_="unique")
        batch_op.drop_index(batch_op.f("ix_resource_entitlements_user_id"))
        batch_op.drop_constraint(
            batch_op.f("fk_resource_entitlements_user_id_users"), type_="foreignkey"
        )
        batch_op.drop_column("user_id")
        batch_op.add_column(sa.Column("workspace_id", _ID, nullable=True))
        batch_op.create_index(
            batch_op.f("ix_resource_entitlements_workspace_id"), ["workspace_id"], unique=False
        )
        batch_op.create_unique_constraint("uq_entitlement", ["workspace_id", "compute_plan_id"])
