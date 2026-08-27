"""Project Version clean cutover 到完整 Git commit OID。

旧 blob manifest 无法证明真实 Git repository 与 commit identity。升级只允许空开发
状态；发现任一 Project graph 数据时必须成对重建数据库与 storage，避免留下悬空状态。

Revision ID: a1f0e2d3c4b5
Revises: f42a9c7e1d30
Create Date: 2026-08-10 11:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1f0e2d3c4b5"
down_revision: str | None = "f42a9c7e1d30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_PROJECT_GRAPH_TABLES = (
    "projects",
    "project_versions",
    "project_files",
    "project_version_files",
    "run_configurations",
    "run_snapshots",
    "runs",
    "run_events",
    "artifacts",
    "fork_relations",
)


def _require_empty_project_graph(direction: str) -> None:
    connection = op.get_bind()
    existing = set(sa.inspect(connection).get_table_names())
    populated = [
        table
        for table in _PROJECT_GRAPH_TABLES
        if table in existing
        and connection.execute(sa.text(f'SELECT 1 FROM "{table}" LIMIT 1')).first() is not None
    ]
    if populated:
        names = ", ".join(populated)
        raise RuntimeError(
            f"Project Git clean cutover {direction} refused: populated tables: {names}. "
            "Rebuild the database and project storage together."
        )


def upgrade() -> None:
    _require_empty_project_graph("upgrade")
    op.drop_table("project_version_files")
    op.drop_table("project_files")

    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("repository_identity", sa.String(length=64), nullable=False))
        batch_op.create_unique_constraint(
            "uq_projects_repository_identity", ["repository_identity"]
        )

    with op.batch_alter_table("project_versions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("repository_identity", sa.String(length=64), nullable=False))
        batch_op.add_column(sa.Column("commit_oid", sa.String(length=64), nullable=False))
        batch_op.add_column(sa.Column("tree_oid", sa.String(length=64), nullable=False))
        batch_op.add_column(sa.Column("file_count", sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column("total_size", sa.Integer(), nullable=False))
        batch_op.create_check_constraint(
            "ck_version_commit_oid_length", "length(commit_oid) IN (40, 64)"
        )
        batch_op.create_check_constraint(
            "ck_version_tree_oid_length", "length(tree_oid) IN (40, 64)"
        )
        batch_op.create_check_constraint("ck_version_file_count_nonnegative", "file_count >= 0")
        batch_op.create_check_constraint("ck_version_total_size_nonnegative", "total_size >= 0")
        batch_op.create_unique_constraint("uq_version_commit_oid", ["project_id", "commit_oid"])


def downgrade() -> None:
    _require_empty_project_graph("downgrade")
    with op.batch_alter_table("project_versions", schema=None) as batch_op:
        batch_op.drop_constraint("uq_version_commit_oid", type_="unique")
        batch_op.drop_constraint("ck_version_total_size_nonnegative", type_="check")
        batch_op.drop_constraint("ck_version_file_count_nonnegative", type_="check")
        batch_op.drop_constraint("ck_version_tree_oid_length", type_="check")
        batch_op.drop_constraint("ck_version_commit_oid_length", type_="check")
        batch_op.drop_column("tree_oid")
        batch_op.drop_column("total_size")
        batch_op.drop_column("file_count")
        batch_op.drop_column("repository_identity")
        batch_op.drop_column("commit_oid")

    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_constraint("uq_projects_repository_identity", type_="unique")
        batch_op.drop_column("repository_identity")

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
