"""Remove Workspace compatibility and converge current owner projections.

Issue #42 is a development-only schema cutover.  Incompatible project execution,
activity, notification, fork, and scoped-config state is deleted in foreign-key-safe
order; no Workspace rows or payloads are converted.  Users, User Groups, Memberships,
assets, Grants, Compute Plans, and User entitlements remain current upstream state.

Downgrade recreates the predecessor schema shape with empty incompatible state only.

Revision ID: f42a9c7e1d30
Revises: a41b9c3e7d2f
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f42a9c7e1d30"
down_revision: str | None = "a41b9c3e7d2f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ID = sa.String(length=40)

_INCOMPATIBLE_STATE_DELETE_ORDER = (
    "run_secret_redactions",
    "artifacts",
    "run_events",
    "idempotency_keys",
    "activities",
    "notifications",
    "fork_relations",
    "runs",
    "run_snapshots",
    "run_configurations",
    "project_version_files",
    "project_versions",
    "project_files",
    "variables",
    "secrets",
    "projects",
)


def _clear_incompatible_state() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in _INCOMPATIBLE_STATE_DELETE_ORDER:
        if inspector.has_table(table):
            bind.execute(sa.text(f'DELETE FROM "{table}"'))


def _drop_if_present(table: str) -> None:
    if sa.inspect(op.get_bind()).has_table(table):
        op.drop_table(table)


def _create_current_activities() -> None:
    op.create_table(
        "activities",
        sa.Column("id", _ID, nullable=False),
        sa.Column("owner_user_id", _ID, nullable=True),
        sa.Column("owner_user_group_id", _ID, nullable=True),
        sa.Column("project_id", _ID, nullable=True),
        sa.Column("actor_id", _ID, nullable=False),
        sa.Column("actor_name", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", _ID, nullable=False),
        sa.Column("target_name", sa.String(length=255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "((owner_user_id IS NOT NULL AND owner_user_group_id IS NULL) "
            "OR (owner_user_id IS NULL AND owner_user_group_id IS NOT NULL))",
            name="ck_activities_exactly_one_owner",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name="fk_activities_owner_user_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_group_id"],
            ["user_groups.id"],
            name="fk_activities_owner_user_group_id_user_groups",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_activities_owner_user_created", "activities", ["owner_user_id", "created_at"]
    )
    op.create_index(
        "ix_activities_owner_user_group_created",
        "activities",
        ["owner_user_group_id", "created_at"],
    )
    op.create_index("ix_activities_project_created", "activities", ["project_id", "created_at"])


def _create_legacy_activities() -> None:
    op.create_table(
        "activities",
        sa.Column("id", _ID, nullable=False),
        sa.Column("workspace_id", _ID, nullable=False),
        sa.Column("project_id", _ID, nullable=True),
        sa.Column("actor_id", _ID, nullable=False),
        sa.Column("actor_name", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", _ID, nullable=False),
        sa.Column("target_name", sa.String(length=255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_activities_workspace_created", "activities", ["workspace_id", "created_at"]
    )
    op.create_index("ix_activities_project_created", "activities", ["project_id", "created_at"])


def upgrade() -> None:
    _clear_incompatible_state()

    op.drop_table("activities")
    _create_current_activities()

    with op.batch_alter_table("projects", recreate="always") as batch:
        batch.drop_constraint("uq_project_name", type_="unique")
        batch.drop_index("ix_projects_workspace_id")
        batch.drop_column("workspace_id")
    op.create_index(
        "uq_projects_owner_user_name",
        "projects",
        ["owner_user_id", "name"],
        unique=True,
        sqlite_where=sa.text("owner_user_id IS NOT NULL"),
        postgresql_where=sa.text("owner_user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_projects_owner_user_group_name",
        "projects",
        ["owner_user_group_id", "name"],
        unique=True,
        sqlite_where=sa.text("owner_user_group_id IS NOT NULL"),
        postgresql_where=sa.text("owner_user_group_id IS NOT NULL"),
    )

    with op.batch_alter_table("runs", recreate="always") as batch:
        batch.drop_index("ix_runs_workspace_id")
        batch.drop_column("workspace_id")
    with op.batch_alter_table("artifacts", recreate="always") as batch:
        batch.drop_index("ix_artifacts_workspace_id")
        batch.drop_column("workspace_id")
    with op.batch_alter_table("notifications", recreate="always") as batch:
        batch.drop_column("workspace_id")
    with op.batch_alter_table("fork_relations", recreate="always") as batch:
        batch.drop_column("source_workspace_id")
        batch.add_column(sa.Column("source_owner_user_id", _ID, nullable=True))
        batch.add_column(sa.Column("source_owner_user_group_id", _ID, nullable=True))
        batch.create_check_constraint(
            "ck_fork_relations_exactly_one_source_owner",
            "((source_owner_user_id IS NOT NULL AND source_owner_user_group_id IS NULL) "
            "OR (source_owner_user_id IS NULL AND source_owner_user_group_id IS NOT NULL))",
        )

    _drop_if_present("legacy_personal_memberships")
    _drop_if_present("user_group_migration_provenance")
    op.drop_table("workspaces")


def downgrade() -> None:
    _clear_incompatible_state()

    op.create_table(
        "workspaces",
        sa.Column("id", _ID, nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner_id", _ID, nullable=False),
        sa.Column("default_environment_version_id", _ID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"])
    op.create_index("ix_workspaces_owner_kind", "workspaces", ["owner_id", "kind"])
    op.create_index(
        "uq_personal_workspace",
        "workspaces",
        ["owner_id"],
        unique=True,
        sqlite_where=sa.text("kind = 'personal'"),
        postgresql_where=sa.text("kind = 'personal'"),
    )

    op.drop_table("activities")
    _create_legacy_activities()

    op.drop_index("uq_projects_owner_user_group_name", table_name="projects")
    op.drop_index("uq_projects_owner_user_name", table_name="projects")
    with op.batch_alter_table("projects", recreate="always") as batch:
        batch.add_column(sa.Column("workspace_id", _ID, nullable=False))
        batch.create_foreign_key(
            "fk_projects_workspace_id_workspaces", "workspaces", ["workspace_id"], ["id"]
        )
        batch.create_unique_constraint("uq_project_name", ["workspace_id", "name"])
        batch.create_index("ix_projects_workspace_id", ["workspace_id"])
    with op.batch_alter_table("runs", recreate="always") as batch:
        batch.add_column(sa.Column("workspace_id", _ID, nullable=False))
        batch.create_foreign_key(
            "fk_runs_workspace_id_workspaces", "workspaces", ["workspace_id"], ["id"]
        )
        batch.create_index("ix_runs_workspace_id", ["workspace_id"])
    with op.batch_alter_table("artifacts", recreate="always") as batch:
        batch.add_column(sa.Column("workspace_id", _ID, nullable=False))
        batch.create_index("ix_artifacts_workspace_id", ["workspace_id"])
    with op.batch_alter_table("notifications", recreate="always") as batch:
        batch.add_column(sa.Column("workspace_id", _ID, nullable=True))
    with op.batch_alter_table("fork_relations", recreate="always") as batch:
        batch.drop_constraint("ck_fork_relations_exactly_one_source_owner", type_="check")
        batch.drop_column("source_owner_user_group_id")
        batch.drop_column("source_owner_user_id")
        batch.add_column(sa.Column("source_workspace_id", _ID, nullable=False))

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
    op.create_table(
        "user_group_migration_provenance",
        sa.Column("user_group_id", _ID, nullable=False),
        sa.Column("created_by_id", _ID, nullable=True),
        sa.PrimaryKeyConstraint("user_group_id"),
    )
