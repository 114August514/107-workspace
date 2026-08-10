"""建立 single-active Independent Worker 的最小 execution intent。

Revision ID: e3b7c91a4d20
Revises: a1f0e2d3c4b5
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from workspace107.infrastructure.db.migration_guards import (
    guard_worker_downgrade,
    guard_worker_upgrade,
)

revision: str = "e3b7c91a4d20"
down_revision: str | None = "a1f0e2d3c4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    guard_worker_upgrade(op.get_bind())
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "ck_runs_status",
            "status IN ('queued','running','succeeded','failed','cancelled','submit_failed')",
        )
        batch_op.create_check_constraint(
            "ck_runs_scheduler_link",
            "((scheduler_job_id IS NULL AND submitted_at IS NULL) OR "
            "(scheduler_job_id IS NOT NULL AND submitted_at IS NOT NULL))",
        )
        batch_op.create_check_constraint(
            "ck_runs_running_has_job", "status <> 'running' OR scheduler_job_id IS NOT NULL"
        )
        batch_op.create_check_constraint(
            "ck_runs_finished_at",
            "((status IN ('queued','running') AND finished_at IS NULL) OR "
            "(status IN ('succeeded','failed','cancelled','submit_failed') "
            "AND finished_at IS NOT NULL))",
        )

    op.create_table(
        "run_execution_intents",
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("correlation", sa.String(length=128), nullable=False),
        sa.Column("attempt_no", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uncertainty_code", sa.String(length=64), nullable=True),
        sa.Column("uncertainty_detail", sa.Text(), server_default="", nullable=False),
        sa.Column("observed_scheduler_state", sa.String(length=24), nullable=True),
        sa.Column("observed_exit_code", sa.Integer(), nullable=True),
        sa.Column("observed_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempt_no >= 0", name="ck_execution_intent_attempt_no"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("run_id"),
        sa.UniqueConstraint("correlation", name="uq_execution_intent_correlation"),
    )
    op.create_index(
        "ix_execution_intents_due",
        "run_execution_intents",
        ["next_action_at", "created_at"],
        unique=False,
    )

    with op.batch_alter_table("artifacts", schema=None) as batch_op:
        batch_op.create_unique_constraint("uq_artifact_run_source_path", ["run_id", "source_path"])


def downgrade() -> None:
    guard_worker_downgrade(op.get_bind())
    with op.batch_alter_table("artifacts", schema=None) as batch_op:
        batch_op.drop_constraint("uq_artifact_run_source_path", type_="unique")

    op.drop_index("ix_execution_intents_due", table_name="run_execution_intents")
    op.drop_table("run_execution_intents")

    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_runs_finished_at", type_="check")
        batch_op.drop_constraint("ck_runs_running_has_job", type_="check")
        batch_op.drop_constraint("ck_runs_scheduler_link", type_="check")
        batch_op.drop_constraint("ck_runs_status", type_="check")
