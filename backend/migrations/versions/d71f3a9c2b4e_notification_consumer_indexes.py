"""Index current Environment consumers for availability notifications.

Project defaults and saved Run Configurations are the current dependency surface for this
notification. Historical Run Snapshots remain execution facts and are intentionally excluded.

Revision ID: d71f3a9c2b4e
Revises: f50a9b7c6d5e
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d71f3a9c2b4e"
down_revision: str | None = "f50a9b7c6d5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_projects_environment_version_id", "projects", ["environment_version_id"])
    op.create_index(
        "ix_run_configurations_environment_version_id",
        "run_configurations",
        ["environment_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_run_configurations_environment_version_id", table_name="run_configurations")
    op.drop_index("ix_projects_environment_version_id", table_name="projects")
