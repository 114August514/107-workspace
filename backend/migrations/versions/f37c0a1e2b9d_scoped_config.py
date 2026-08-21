"""Migrate Workspace config rows to explicit User/UserGroup/Project scopes."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f37c0a1e2b9d"
down_revision: str | None = "e35a1d7c9b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _scope_for_workspace(bind: sa.Connection, workspace_id: str) -> tuple[str, str]:
    row = (
        bind.execute(
            sa.text("SELECT kind, owner_id FROM workspaces WHERE id=:id"), {"id": workspace_id}
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise RuntimeError(f"orphan Workspace config: {workspace_id}")
    if row["kind"] == "personal":
        anchors = bind.execute(
            sa.text("SELECT COUNT(*) FROM workspaces WHERE kind='personal' AND owner_id=:id"),
            {"id": row["owner_id"]},
        ).scalar_one()
        user = bind.execute(
            sa.text("SELECT 1 FROM users WHERE id=:id"), {"id": row["owner_id"]}
        ).first()
        if anchors != 1 or user is None:
            raise RuntimeError(f"personal Workspace owner/anchor is not provable: {workspace_id}")
        return "user", row["owner_id"]
    if row["kind"] == "collaborative":
        group = bind.execute(
            sa.text("SELECT 1 FROM user_groups WHERE id=:id"), {"id": workspace_id}
        ).first()
        owner = bind.execute(
            sa.text(
                "SELECT 1 FROM memberships "
                "WHERE user_group_id=:id AND role='owner' AND status='active'"
            ),
            {"id": workspace_id},
        ).first()
        if group is None or owner is None:
            raise RuntimeError(
                f"collaborative Workspace group/active owner is not provable: {workspace_id}"
            )
        return "user_group", workspace_id
    raise RuntimeError(f"unprovable Workspace kind: {workspace_id}: {row['kind']}")


def _create_scoped_tables() -> None:
    op.create_table(
        "variables",
        sa.Column("scope_kind", sa.String(32), nullable=False),
        sa.Column("scope_id", sa.String(40), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("scope_kind", "scope_id", "name"),
    )
    op.create_table(
        "secrets",
        sa.Column("scope_kind", sa.String(32), nullable=False),
        sa.Column("scope_id", sa.String(40), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("scope_kind", "scope_id", "name"),
    )


def upgrade() -> None:
    bind = op.get_bind()
    _create_scoped_tables()
    for source, target in (("workspace_variables", "variables"), ("workspace_secrets", "secrets")):
        for row in bind.execute(sa.text(f"SELECT * FROM {source}")).mappings().all():
            kind, scope_id = _scope_for_workspace(bind, row["workspace_id"])
            columns = "scope_kind,scope_id,name,value" + (
                ",updated_at" if target == "secrets" else ""
            )
            values = ":kind,:scope_id,:name,:value" + (
                ",:updated_at" if target == "secrets" else ""
            )
            bind.execute(
                sa.text(f"INSERT INTO {target} ({columns}) VALUES ({values})"),
                {
                    "kind": kind,
                    "scope_id": scope_id,
                    "name": row["name"],
                    "value": row["value"],
                    "updated_at": row.get("updated_at"),
                },
            )
    op.drop_table("workspace_variables")
    op.drop_table("workspace_secrets")


def downgrade() -> None:
    bind = op.get_bind()
    for kind in ("project",):
        if (
            bind.execute(
                sa.text("SELECT 1 FROM variables WHERE scope_kind=:kind LIMIT 1"), {"kind": kind}
            ).first()
            or bind.execute(
                sa.text("SELECT 1 FROM secrets WHERE scope_kind=:kind LIMIT 1"), {"kind": kind}
            ).first()
        ):
            raise RuntimeError("cannot downgrade Project-scoped config to Workspace scope")
    op.create_table(
        "workspace_variables",
        sa.Column("workspace_id", sa.String(40), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("workspace_id", "name"),
    )
    op.create_table(
        "workspace_secrets",
        sa.Column("workspace_id", sa.String(40), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("workspace_id", "name"),
    )
    for source, target in (("variables", "workspace_variables"), ("secrets", "workspace_secrets")):
        for row in bind.execute(sa.text(f"SELECT * FROM {source}")).mappings().all():
            if row["scope_kind"] == "user":
                stmt = sa.text("SELECT id FROM workspaces WHERE kind='personal' AND owner_id=:id")
            elif row["scope_kind"] == "user_group":
                stmt = sa.text("SELECT id FROM workspaces WHERE kind='collaborative' AND id=:id")
            else:
                raise RuntimeError(f"unknown or non-legacy scope: {row['scope_kind']}")
            workspace = bind.execute(stmt, {"id": row["scope_id"]}).scalars().all()
            if len(workspace) != 1:
                raise RuntimeError(
                    f"cannot reverse scoped config {row['scope_kind']}:{row['scope_id']}"
                )
            columns = "workspace_id,name,value" + (
                ",updated_at" if target == "workspace_secrets" else ""
            )
            values = ":workspace_id,:name,:value" + (
                ",:updated_at" if target == "workspace_secrets" else ""
            )
            bind.execute(
                sa.text(f"INSERT INTO {target} ({columns}) VALUES ({values})"),
                {
                    "workspace_id": workspace[0],
                    "name": row["name"],
                    "value": row["value"],
                    "updated_at": row.get("updated_at"),
                },
            )
    op.drop_table("variables")
    op.drop_table("secrets")
