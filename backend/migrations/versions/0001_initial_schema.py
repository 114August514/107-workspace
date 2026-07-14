"""Create the initial workspace schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_workspaces_created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["workspaces.id"], name="fk_workspaces_parent_id", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
        sa.UniqueConstraint("slug", name="uq_workspaces_slug"),
    )
    op.create_index("ix_workspaces_created_by", "workspaces", ["created_by"])
    op.create_index("ix_workspaces_parent_id", "workspaces", ["parent_id"])
    op.create_table(
        "workspace_members",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_workspace_members_user_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_workspace_members_workspace_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("workspace_id", "user_id", name="pk_workspace_members"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
    )
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_projects_created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_projects_workspace_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_projects_workspace_slug"),
    )
    op.create_index("ix_projects_created_by", "projects", ["created_by"])
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])
    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_datasets_created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_datasets_workspace_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_datasets"),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_datasets_workspace_slug"),
    )
    op.create_index("ix_datasets_created_by", "datasets", ["created_by"])
    op.create_index("ix_datasets_workspace_id", "datasets", ["workspace_id"])
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_dataset_versions_created_by",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_dataset_versions_dataset_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_versions"),
        sa.UniqueConstraint("dataset_id", "version", name="uq_dataset_versions_dataset_version"),
    )
    op.create_index("ix_dataset_versions_created_by", "dataset_versions", ["created_by"])
    op.create_index("ix_dataset_versions_dataset_id", "dataset_versions", ["dataset_id"])
    op.create_index("ix_dataset_versions_storage_key", "dataset_versions", ["storage_key"])
    op.create_table(
        "run_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("entrypoint", sa.String(length=500), nullable=False),
        sa.Column("environment_spec", sa.JSON(), nullable=False),
        sa.Column("resource_spec", sa.JSON(), nullable=False),
        sa.Column("output_spec", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_run_templates_created_by",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_run_templates_workspace_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_run_templates"),
    )
    op.create_index("ix_run_templates_created_by", "run_templates", ["created_by"])
    op.create_index("ix_run_templates_workspace_id", "run_templates", ["workspace_id"])
    op.create_table(
        "runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("submitted_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("external_job_id", sa.String(length=200), nullable=True),
        sa.Column("submission_snapshot", sa.JSON(), nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_runs_project_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"], ["users.id"], name="fk_runs_submitted_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["run_templates.id"],
            name="fk_runs_template_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_runs_workspace_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_runs"),
    )
    op.create_index("ix_runs_external_job_id", "runs", ["external_job_id"])
    op.create_index("ix_runs_project_id", "runs", ["project_id"])
    op.create_index("ix_runs_status", "runs", ["status"])
    op.create_index("ix_runs_submitted_by", "runs", ["submitted_by"])
    op.create_index("ix_runs_template_id", "runs", ["template_id"])
    op.create_index("ix_runs_workspace_id", "runs", ["workspace_id"])
    op.create_table(
        "run_datasets",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("mount_path", sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["dataset_versions.id"],
            name="fk_run_datasets_dataset_version_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name="fk_run_datasets_run_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("run_id", "mount_path", name="pk_run_datasets"),
        sa.UniqueConstraint("run_id", "mount_path", name="uq_run_datasets_run_mount_path"),
    )
    op.create_index("ix_run_datasets_dataset_version_id", "run_datasets", ["dataset_version_id"])
    op.create_table(
        "run_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name="fk_run_events_run_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_run_events"),
    )
    op.create_index("ix_run_events_run_id_created_at", "run_events", ["run_id", "created_at"])
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("media_type", sa.String(length=200), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name="fk_artifacts_run_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_artifacts"),
    )
    op.create_index("ix_artifacts_run_id", "artifacts", ["run_id"])
    op.create_index("ix_artifacts_storage_key", "artifacts", ["storage_key"])
    op.create_table(
        "project_syncs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("transport", sa.String(length=32), nullable=False),
        sa.Column("target_uri", sa.String(length=1000), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_syncs_project_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_syncs"),
        sa.UniqueConstraint(
            "project_id", "transport", "target_uri", name="uq_project_syncs_target"
        ),
    )
    op.create_index("ix_project_syncs_project_id", "project_syncs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_syncs_project_id", table_name="project_syncs")
    op.drop_table("project_syncs")
    op.drop_index("ix_artifacts_storage_key", table_name="artifacts")
    op.drop_index("ix_artifacts_run_id", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_run_events_run_id_created_at", table_name="run_events")
    op.drop_table("run_events")
    op.drop_index("ix_run_datasets_dataset_version_id", table_name="run_datasets")
    op.drop_table("run_datasets")
    op.drop_index("ix_runs_workspace_id", table_name="runs")
    op.drop_index("ix_runs_template_id", table_name="runs")
    op.drop_index("ix_runs_submitted_by", table_name="runs")
    op.drop_index("ix_runs_status", table_name="runs")
    op.drop_index("ix_runs_project_id", table_name="runs")
    op.drop_index("ix_runs_external_job_id", table_name="runs")
    op.drop_table("runs")
    op.drop_index("ix_run_templates_workspace_id", table_name="run_templates")
    op.drop_index("ix_run_templates_created_by", table_name="run_templates")
    op.drop_table("run_templates")
    op.drop_index("ix_dataset_versions_storage_key", table_name="dataset_versions")
    op.drop_index("ix_dataset_versions_dataset_id", table_name="dataset_versions")
    op.drop_index("ix_dataset_versions_created_by", table_name="dataset_versions")
    op.drop_table("dataset_versions")
    op.drop_index("ix_datasets_workspace_id", table_name="datasets")
    op.drop_index("ix_datasets_created_by", table_name="datasets")
    op.drop_table("datasets")
    op.drop_index("ix_projects_workspace_id", table_name="projects")
    op.drop_index("ix_projects_created_by", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_workspace_members_user_id", table_name="workspace_members")
    op.drop_table("workspace_members")
    op.drop_index("ix_workspaces_parent_id", table_name="workspaces")
    op.drop_index("ix_workspaces_created_by", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_table("users")
