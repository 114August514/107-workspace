"""Replace legacy asset ownership with User/UserGroup ownership.

This revision intentionally discards every Environment and Shared Resource database
aggregate approved as disposable by Issue #39. Upgrade deletes child rows before
parents, then establishes empty owner-constrained tables. It does not inspect,
delete, or garbage-collect content-addressed blobs.

Workspace, Project, Run Configuration, and Run Snapshot references are deliberately
left byte-for-byte/JSON-semantically unchanged. They have no database foreign keys to
asset versions and therefore become truthful unavailable exact references. New seed
versions must use new IDs; recreating a deleted ID would silently retarget history.

Downgrade is explicitly non-lossless: it again deletes all asset aggregates child-first
and restores only the empty legacy schema. Neither downgrade nor a Git revert can
recover discarded metadata; recovery requires a pre-migration database backup.

Revision ID: c471ac39f002
Revises: e35a1d7c9b20
Create Date: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c471ac39f002"
down_revision: str | None = "e35a1d7c9b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ID = sa.String(length=40)


def _assert_sqlite_foreign_keys() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    if bind.exec_driver_sql("PRAGMA foreign_keys").scalar_one() != 1:
        raise RuntimeError("asset ownership migration requires SQLite foreign key enforcement")


def _delete_asset_aggregates() -> None:
    op.execute(sa.text("DELETE FROM shared_resource_version_files"))
    op.execute(sa.text("DELETE FROM shared_resource_versions"))
    op.execute(sa.text("DELETE FROM shared_resources"))
    op.execute(sa.text("DELETE FROM environment_versions"))
    op.execute(sa.text("DELETE FROM environments"))


def _add_owner_columns(table: str) -> None:
    with op.batch_alter_table(table, schema=None) as batch_op:
        batch_op.drop_column("owner_workspace_id")
        batch_op.add_column(sa.Column("owner_user_id", _ID, nullable=True))
        batch_op.add_column(sa.Column("owner_user_group_id", _ID, nullable=True))
        batch_op.create_foreign_key(
            f"fk_{table}_owner_user_id_users",
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            f"fk_{table}_owner_user_group_id_user_groups",
            "user_groups",
            ["owner_user_group_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_check_constraint(
            f"ck_{table}_exactly_one_owner",
            "((owner_user_id IS NOT NULL AND owner_user_group_id IS NULL) "
            "OR (owner_user_id IS NULL AND owner_user_group_id IS NOT NULL))",
        )
        batch_op.create_index(f"ix_{table}_owner_user_id", ["owner_user_id"], unique=False)
        batch_op.create_index(
            f"ix_{table}_owner_user_group_id", ["owner_user_group_id"], unique=False
        )


def _restore_legacy_owner_column(table: str) -> None:
    with op.batch_alter_table(table, schema=None) as batch_op:
        batch_op.drop_index(f"ix_{table}_owner_user_group_id")
        batch_op.drop_index(f"ix_{table}_owner_user_id")
        batch_op.drop_constraint(f"ck_{table}_exactly_one_owner", type_="check")
        batch_op.drop_constraint(f"fk_{table}_owner_user_group_id_user_groups", type_="foreignkey")
        batch_op.drop_constraint(f"fk_{table}_owner_user_id_users", type_="foreignkey")
        batch_op.add_column(sa.Column("owner_workspace_id", _ID, nullable=True))
        batch_op.drop_column("owner_user_group_id")
        batch_op.drop_column("owner_user_id")


def upgrade() -> None:
    _assert_sqlite_foreign_keys()
    _delete_asset_aggregates()

    # The old Shared Resource owner column has an explicit index. Environment's does not.
    with op.batch_alter_table("shared_resources", schema=None) as batch_op:
        batch_op.drop_index("ix_shared_resources_owner_workspace_id")

    _add_owner_columns("environments")
    _add_owner_columns("shared_resources")


def downgrade() -> None:
    """Restore only an empty legacy schema; discarded asset metadata is unrecoverable."""

    _assert_sqlite_foreign_keys()
    _delete_asset_aggregates()
    _restore_legacy_owner_column("environments")
    _restore_legacy_owner_column("shared_resources")

    with op.batch_alter_table("shared_resources", schema=None) as batch_op:
        batch_op.create_index(
            "ix_shared_resources_owner_workspace_id", ["owner_workspace_id"], unique=False
        )
