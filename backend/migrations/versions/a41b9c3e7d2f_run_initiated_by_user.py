"""Converge Run semantics on Initiated By User and exact Environment Version.

Issue #41 is a development-stage destructive cutover. Upgrade and downgrade keep
their respective schema contracts but discard incompatible Run execution,
configuration, Snapshot, and idempotency state instead of converting payloads.

Revision ID: a41b9c3e7d2f
Revises: f36a1b2c3d4e
Create Date: 2026-08-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a41b9c3e7d2f"
down_revision: str | None = "f36a1b2c3d4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _clear_execution_state() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE projects SET default_run_configuration_id = NULL "
            "WHERE default_run_configuration_id IS NOT NULL"
        )
    )
    connection.execute(sa.text("DELETE FROM idempotency_keys"))
    connection.execute(sa.text("DELETE FROM run_secret_redactions"))
    connection.execute(sa.text("DELETE FROM run_events"))
    connection.execute(sa.text("DELETE FROM artifacts"))
    connection.execute(sa.text("DELETE FROM runs"))
    connection.execute(sa.text("DELETE FROM run_snapshots"))
    connection.execute(sa.text("DELETE FROM run_configurations"))


def upgrade() -> None:
    _clear_execution_state()

    op.drop_index("ix_runs_created_by", table_name="runs")
    with op.batch_alter_table("runs") as batch:
        batch.alter_column(
            "created_by", new_column_name="initiated_by_user_id", existing_type=sa.String(40)
        )
    op.create_index("ix_runs_initiated_by_user_id", "runs", ["initiated_by_user_id"])

    with op.batch_alter_table("run_configurations") as batch:
        batch.alter_column("environment_version_id", existing_type=sa.String(40), nullable=False)

    op.drop_table("idempotency_keys")
    op.create_table(
        "idempotency_keys",
        sa.Column("initiated_by_user_id", sa.String(length=40), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("endpoint", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("initiated_by_user_id", "key"),
    )


def downgrade() -> None:
    _clear_execution_state()

    op.drop_table("idempotency_keys")
    op.create_table(
        "idempotency_keys",
        sa.Column("workspace_id", sa.String(length=40), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("endpoint", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("workspace_id", "key"),
    )

    with op.batch_alter_table("run_configurations") as batch:
        batch.alter_column("environment_version_id", existing_type=sa.String(40), nullable=True)

    op.drop_index("ix_runs_initiated_by_user_id", table_name="runs")
    with op.batch_alter_table("runs") as batch:
        batch.alter_column(
            "initiated_by_user_id", new_column_name="created_by", existing_type=sa.String(40)
        )
    op.create_index("ix_runs_created_by", "runs", ["created_by"])
