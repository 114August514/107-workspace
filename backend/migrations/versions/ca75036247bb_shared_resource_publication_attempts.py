"""Add durable Shared Resource publication attempts.

This migration runs under the currently and explicitly authorized destructive development
cutover: no existing data must be preserved. It deletes every row from
shared_resource_version_files and shared_resource_versions because those versions were
published without processor validation and must not be represented as validated versions.

Revision ID: ca75036247bb
Revises: f42a9c7e1d30
Create Date: 2026-08-24 11:51:51.159322
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ca75036247bb"
down_revision: str | None = "f42a9c7e1d30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The authorized development cutover deletes all pre-validation Version and file rows.
    op.execute(sa.text("DELETE FROM shared_resource_version_files"))
    op.execute(sa.text("DELETE FROM shared_resource_versions"))

    with op.batch_alter_table("shared_resource_versions") as batch_op:
        batch_op.add_column(sa.Column("manifest_hash", sa.String(length=64), nullable=False))
        batch_op.add_column(sa.Column("validation_summary", sa.Text(), nullable=False))

    op.create_table(
        "shared_resource_publication_attempts",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "shared_resource_id",
            sa.String(length=32),
            sa.ForeignKey("shared_resources.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("validation_summary", sa.Text(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "version_id",
            sa.String(length=32),
            sa.ForeignKey("shared_resource_versions.id"),
            nullable=True,
            unique=True,
        ),
        sa.Column("created_by", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'succeeded', 'failed')",
            name="ck_shared_resource_publication_attempt_status",
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND started_at IS NULL AND finished_at IS NULL "
            "AND version_id IS NULL AND failure_reason IS NULL) OR "
            "(status = 'processing' AND started_at IS NOT NULL AND finished_at IS NULL "
            "AND version_id IS NULL AND failure_reason IS NULL) OR "
            "(status = 'succeeded' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND version_id IS NOT NULL AND failure_reason IS NULL) OR "
            "(status = 'failed' AND started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND version_id IS NULL AND failure_reason IS NOT NULL)",
            name="ck_shared_resource_publication_attempt_result",
        ),
    )
    op.create_index(
        "ix_shared_resource_publication_attempt_claim",
        "shared_resource_publication_attempts",
        ["status", "started_at", "created_at"],
    )
    op.create_index(
        "ix_shared_resource_publication_attempt_resource",
        "shared_resource_publication_attempts",
        ["shared_resource_id", "created_at"],
    )
    op.create_table(
        "shared_resource_publication_files",
        sa.Column(
            "attempt_id",
            sa.String(length=32),
            sa.ForeignKey("shared_resource_publication_attempts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("path", sa.String(length=1024), primary_key=True),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint("size >= 0", name="ck_shared_resource_publication_file_size"),
    )


def downgrade() -> None:
    op.drop_table("shared_resource_publication_files")
    op.drop_index(
        "ix_shared_resource_publication_attempt_resource",
        table_name="shared_resource_publication_attempts",
    )
    op.drop_index(
        "ix_shared_resource_publication_attempt_claim",
        table_name="shared_resource_publication_attempts",
    )
    op.drop_table("shared_resource_publication_attempts")
    with op.batch_alter_table("shared_resource_versions") as batch_op:
        batch_op.drop_column("validation_summary")
        batch_op.drop_column("manifest_hash")
