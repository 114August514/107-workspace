"""Add exact default Environment Version to User Groups.

Revision ID: e45a1c2d3f40
Revises: f42a9c7e1d30
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e45a1c2d3f40"
down_revision: str | None = "f42a9c7e1d30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    column = sa.Column(
        "default_environment_version_id",
        sa.String(length=64),
        sa.ForeignKey(
            "environment_versions.id",
            name="fk_user_groups_default_environment_version",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            sa.text(
                "ALTER TABLE user_groups ADD COLUMN "
                "default_environment_version_id VARCHAR(64) "
                "REFERENCES environment_versions(id) ON DELETE SET NULL"
            )
        )
    else:
        op.add_column("user_groups", column)
    op.create_index(
        "ix_user_groups_default_environment_version_id",
        "user_groups",
        ["default_environment_version_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_groups_default_environment_version_id",
        table_name="user_groups",
    )
    op.drop_column("user_groups", "default_environment_version_id")
