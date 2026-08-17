"""Establish User Group identity and governance persistence.

``legacy_personal_memberships`` exists only at this revision to keep Personal
Workspace Membership rows reversible. ``user_group_migration_provenance``
survives downgrade so a later upgrade can restore known ``created_by_id``.
Both may be deleted only by a dedicated migration after the e35 rollback
window and Personal Workspace compatibility are explicitly retired.

Revision ID: e35a1d7c9b20
Revises: a3f7c2e91b84
Create Date: 2026-08-17
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e35a1d7c9b20"
down_revision: str | None = "a3f7c2e91b84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ID = sa.String(length=40)


def _migration_membership_id(user_group_id: str, user_id: str) -> str:
    digest = hashlib.sha256(f"{user_group_id}:{user_id}".encode()).hexdigest()[:20]
    return f"mbr_{digest}"


def _ensure_provenance_table(bind: sa.Connection) -> None:
    if sa.inspect(bind).has_table("user_group_migration_provenance"):
        return
    op.create_table(
        "user_group_migration_provenance",
        sa.Column("user_group_id", _ID, nullable=False),
        sa.Column("created_by_id", _ID, nullable=True),
        sa.PrimaryKeyConstraint("user_group_id"),
    )


def _remember_creator(bind: sa.Connection, user_group_id: str, created_by_id: str | None) -> None:
    existing = bind.execute(
        sa.text(
            "SELECT user_group_id FROM user_group_migration_provenance "
            "WHERE user_group_id = :user_group_id"
        ),
        {"user_group_id": user_group_id},
    ).first()
    if existing is None:
        bind.execute(
            sa.text(
                "INSERT INTO user_group_migration_provenance "
                "(user_group_id, created_by_id) VALUES (:user_group_id, :created_by_id)"
            ),
            {"user_group_id": user_group_id, "created_by_id": created_by_id},
        )
    else:
        bind.execute(
            sa.text(
                "UPDATE user_group_migration_provenance SET created_by_id = :created_by_id "
                "WHERE user_group_id = :user_group_id"
            ),
            {"user_group_id": user_group_id, "created_by_id": created_by_id},
        )


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_provenance_table(bind)
    known_creators = {
        row["user_group_id"]: row["created_by_id"]
        for row in bind.execute(
            sa.text("SELECT user_group_id, created_by_id FROM user_group_migration_provenance")
        ).mappings()
    }
    op.create_table(
        "user_groups",
        sa.Column("id", _ID, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        # The old Workspace row records current owner, not historical creator.
        # Migrated groups therefore keep this truthfully unknown.
        sa.Column("created_by_id", _ID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_groups_created_by_id", "user_groups", ["created_by_id"])

    op.create_table(
        "memberships_new",
        sa.Column("id", _ID, nullable=False),
        sa.Column("user_group_id", _ID, nullable=False),
        sa.Column("user_id", _ID, nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_group_id"], ["user_groups.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_group_id", "user_id", name="uq_user_group_membership"),
    )

    groups = bind.execute(
        sa.text(
            "SELECT id, name, description, owner_id, created_at "
            "FROM workspaces WHERE kind = 'collaborative' ORDER BY id"
        )
    ).mappings()
    for group in groups:
        created_by_id = known_creators.get(group["id"])
        bind.execute(
            sa.text(
                "INSERT INTO user_groups "
                "(id, name, description, created_by_id, created_at) "
                "VALUES (:id, :name, :description, :created_by_id, :created_at)"
            ),
            {**dict(group), "created_by_id": created_by_id},
        )
        if group["id"] not in known_creators:
            _remember_creator(bind, group["id"], None)
        old_memberships = list(
            bind.execute(
                sa.text(
                    "SELECT id, user_id, role, status, created_at FROM memberships "
                    "WHERE workspace_id = :group_id ORDER BY created_at, id"
                ),
                {"group_id": group["id"]},
            ).mappings()
        )
        owner_seen = False
        for membership in old_memberships:
            is_owner = membership["user_id"] == group["owner_id"]
            owner_seen = owner_seen or is_owner
            role = (
                "owner"
                if is_owner
                else ("admin" if membership["role"] == "owner" else membership["role"])
            )
            status = "active" if is_owner else membership["status"]
            bind.execute(
                sa.text(
                    "INSERT INTO memberships_new "
                    "(id, user_group_id, user_id, role, status, created_at) "
                    "VALUES (:id, :user_group_id, :user_id, :role, :status, :created_at)"
                ),
                {
                    "id": membership["id"],
                    "user_group_id": group["id"],
                    "user_id": membership["user_id"],
                    "role": role,
                    "status": status,
                    "created_at": membership["created_at"],
                },
            )
        if not owner_seen:
            bind.execute(
                sa.text(
                    "INSERT INTO memberships_new "
                    "(id, user_group_id, user_id, role, status, created_at) "
                    "VALUES (:id, :user_group_id, :user_id, 'owner', 'active', :created_at)"
                ),
                {
                    "id": _migration_membership_id(group["id"], group["owner_id"]),
                    "user_group_id": group["id"],
                    "user_id": group["owner_id"],
                    "created_at": group["created_at"],
                },
            )

    op.create_table(
        "legacy_personal_memberships",
        sa.Column("id", _ID, nullable=False),
        sa.Column("workspace_id", _ID, nullable=False),
        sa.Column("user_id", _ID, nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_legacy_personal_membership"),
    )
    bind.execute(
        sa.text(
            "INSERT INTO legacy_personal_memberships "
            "(id, workspace_id, user_id, role, status, created_at) "
            "SELECT m.id, m.workspace_id, m.user_id, m.role, m.status, m.created_at "
            "FROM memberships AS m JOIN workspaces AS w ON w.id = m.workspace_id "
            "WHERE w.kind = 'personal'"
        )
    )
    op.drop_table("memberships")
    op.rename_table("memberships_new", "memberships")
    op.create_index("ix_user_group_memberships_user_group_id", "memberships", ["user_group_id"])
    op.create_index("ix_user_group_memberships_user_id", "memberships", ["user_id"])
    op.create_index(
        "uq_membership_active_owner",
        "memberships",
        ["user_group_id"],
        unique=True,
        sqlite_where=sa.text("role = 'owner' AND status = 'active'"),
        postgresql_where=sa.text("role = 'owner' AND status = 'active'"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    _ensure_provenance_table(bind)
    op.create_table(
        "memberships_old",
        sa.Column("id", _ID, nullable=False),
        sa.Column("workspace_id", _ID, nullable=False),
        sa.Column("user_id", _ID, nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_membership"),
    )

    groups = list(
        bind.execute(
            sa.text("SELECT id, name, description, created_by_id, created_at FROM user_groups")
        ).mappings()
    )
    for group in groups:
        _remember_creator(bind, group["id"], group["created_by_id"])
        owner = bind.execute(
            sa.text(
                "SELECT user_id FROM memberships WHERE user_group_id = :group_id "
                "AND role = 'owner' AND status = 'active'"
            ),
            {"group_id": group["id"]},
        ).scalar_one_or_none()
        if owner is None:
            raise RuntimeError(f"User Group {group['id']} has no active owner; downgrade refused")
        exists = bind.execute(
            sa.text("SELECT 1 FROM workspaces WHERE id = :id"), {"id": group["id"]}
        ).scalar_one_or_none()
        if exists:
            bind.execute(
                sa.text(
                    "UPDATE workspaces SET name = :name, description = :description, "
                    "owner_id = :owner_id WHERE id = :id"
                ),
                {**dict(group), "owner_id": owner},
            )
        else:
            bind.execute(
                sa.text(
                    "INSERT INTO workspaces "
                    "(id, kind, name, description, owner_id, "
                    "default_environment_version_id, created_at) "
                    "VALUES (:id, 'collaborative', :name, :description, "
                    ":owner_id, NULL, :created_at)"
                ),
                {**dict(group), "owner_id": owner},
            )

    bind.execute(
        sa.text(
            "INSERT INTO memberships_old (id, workspace_id, user_id, role, status, created_at) "
            "SELECT id, user_group_id, user_id, role, status, created_at FROM memberships"
        )
    )
    bind.execute(
        sa.text(
            "INSERT INTO memberships_old "
            "(id, workspace_id, user_id, role, status, created_at) "
            "SELECT id, workspace_id, user_id, role, status, created_at "
            "FROM legacy_personal_memberships"
        )
    )
    op.drop_table("memberships")
    op.drop_index("ix_user_groups_created_by_id", table_name="user_groups")
    op.drop_table("user_groups")
    op.rename_table("memberships_old", "memberships")
    op.create_index("ix_memberships_workspace_id", "memberships", ["workspace_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])
    op.drop_table("legacy_personal_memberships")
