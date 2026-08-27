"""Give Project an explicit User/User Group owner and visibility.

Issue #36: Project 的归属从 ``workspace_id`` 迁移为显式 User/UserGroup Owner，
并增加 ``OWNER_SCOPE`` / ``PUBLIC`` Visibility。``workspace_id`` 作为 #37-#42
迁移窗口内的兼容锚点保留，不再是归属权威。

downgrade 只还原表结构，不回填 owner 列——产品尚未投入使用，本地库直接重建。

Revision ID: f36a1b2c3d4e
Revises: 4d7a2f91c3e5
Create Date: 2026-08-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f36a1b2c3d4e"
down_revision: str | None = "4d7a2f91c3e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("owner_user_id", sa.String(40), nullable=True))
    op.add_column("projects", sa.Column("owner_user_group_id", sa.String(40), nullable=True))
    op.add_column(
        "projects",
        sa.Column("visibility", sa.String(32), nullable=False, server_default="owner_scope"),
    )
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT p.id, p.workspace_id, w.kind, w.owner_id "
            "FROM projects p JOIN workspaces w ON w.id = p.workspace_id"
        )
    ).mappings()
    for row in rows:
        if row["kind"] == "personal":
            bind.execute(
                sa.text("UPDATE projects SET owner_user_id = :owner WHERE id = :id"),
                {"owner": row["owner_id"], "id": row["id"]},
            )
        else:
            bind.execute(
                sa.text("UPDATE projects SET owner_user_group_id = :owner WHERE id = :id"),
                {"owner": row["workspace_id"], "id": row["id"]},
            )
    op.create_index("ix_projects_owner_user_id", "projects", ["owner_user_id"])
    op.create_index("ix_projects_owner_user_group_id", "projects", ["owner_user_group_id"])
    # Keep the old workspace anchor during the bounded #37-#42 migration window.
    with op.batch_alter_table("projects") as batch:
        batch.create_foreign_key(
            "fk_projects_owner_user_id_users",
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_projects_owner_user_group_id_user_groups",
            "user_groups",
            ["owner_user_group_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_check_constraint(
            "ck_projects_exactly_one_owner",
            "((owner_user_id IS NOT NULL AND owner_user_group_id IS NULL) "
            "OR (owner_user_id IS NULL AND owner_user_group_id IS NOT NULL))",
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("ck_projects_exactly_one_owner", type_="check")
        batch.drop_constraint("fk_projects_owner_user_group_id_user_groups", type_="foreignkey")
        batch.drop_constraint("fk_projects_owner_user_id_users", type_="foreignkey")
    op.drop_index("ix_projects_owner_user_group_id", table_name="projects")
    op.drop_index("ix_projects_owner_user_id", table_name="projects")
    op.drop_column("projects", "visibility")
    op.drop_column("projects", "owner_user_group_id")
    op.drop_column("projects", "owner_user_id")
