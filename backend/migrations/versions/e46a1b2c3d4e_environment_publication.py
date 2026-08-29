"""Replace generic Environment image/setup semantics with exact publication state.

This development migration intentionally deletes Environment Version-dependent Run,
Run Snapshot, Run Configuration, event, artifact, redaction, and idempotency rows plus
all Environment Versions. Activity and Notification history is preserved. No Environment
Version data is preserved; downgrade restores only the predecessor schema shape.

Revision ID: e46a1b2c3d4e
Revises: f42a9c7e1d30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e46a1b2c3d4e"
down_revision: str | None = "f42a9c7e1d30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ID = sa.String(length=40)


def _clear_execution_state() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in (
        "run_secret_redactions",
        "artifacts",
        "run_events",
        "idempotency_keys",
        "runs",
        "run_snapshots",
        "run_configurations",
        "environment_publication_attempts",
        "environment_versions",
    ):
        if inspector.has_table(table):
            bind.execute(sa.text(f'DELETE FROM "{table}"'))


def upgrade() -> None:
    _clear_execution_state()
    op.drop_table("environment_versions")
    op.create_table(
        "environment_versions",
        sa.Column("id", _ID, primary_key=True),
        sa.Column("environment_id", _ID, sa.ForeignKey("environments.id"), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("runtime_kind", sa.String(32), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("definition_hash", sa.String(64), nullable=False),
        sa.Column("execution_spec", sa.JSON(), nullable=False),
        sa.Column("validation_summary", sa.Text(), nullable=False),
        sa.Column("validation_evidence", sa.JSON(), nullable=False),
        sa.Column("availability", sa.String(32), nullable=False),
        sa.Column("availability_reason", sa.String(128), nullable=False, server_default=""),
        sa.Column("availability_detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("availability_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("environment_id", "version", name="uq_environment_version_label"),
        sa.CheckConstraint(
            "runtime_kind IN ('modules', 'apptainer_sif')",
            name="ck_environment_versions_runtime_kind",
        ),
        sa.CheckConstraint(
            "availability IN ('available', 'unavailable', 'deprecated')",
            name="ck_environment_versions_availability",
        ),
    )
    op.create_index(
        "ix_environment_versions_environment_id", "environment_versions", ["environment_id"]
    )
    op.create_table(
        "environment_publication_attempts",
        sa.Column("id", _ID, primary_key=True),
        sa.Column("environment_id", _ID, sa.ForeignKey("environments.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("runtime_kind", sa.String(32), nullable=False),
        sa.Column("candidate_definition", sa.JSON(), nullable=False),
        sa.Column("validation_summary", sa.Text(), nullable=False),
        sa.Column("validation_evidence", sa.JSON(), nullable=False),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("version_id", _ID, sa.ForeignKey("environment_versions.id"), nullable=True),
        sa.Column("created_by", _ID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'succeeded', 'failed')",
            name="ck_environment_publication_attempts_status",
        ),
        sa.CheckConstraint(
            "runtime_kind IN ('modules', 'apptainer_sif')",
            name="ck_environment_publication_attempts_runtime_kind",
        ),
    )
    op.create_index(
        "ix_environment_publication_attempts_environment_id",
        "environment_publication_attempts",
        ["environment_id"],
    )
    op.create_index(
        "ix_environment_publication_attempts_status", "environment_publication_attempts", ["status"]
    )


def downgrade() -> None:
    _clear_execution_state()
    op.drop_table("environment_publication_attempts")
    op.drop_table("environment_versions")
    op.create_table(
        "environment_versions",
        sa.Column("id", _ID, primary_key=True),
        sa.Column("environment_id", _ID, sa.ForeignKey("environments.id"), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("image", sa.String(255), nullable=False),
        sa.Column("setup_command", sa.Text(), nullable=False, server_default=""),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_environment_versions_environment_id", "environment_versions", ["environment_id"]
    )
