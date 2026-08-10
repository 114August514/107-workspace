"""建立 Independent Worker execution intent、submission attempt 与恢复约束。

Revision ID: e3b7c91a4d20
Revises: b48640074b91
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3b7c91a4d20"
down_revision: str | None = "b48640074b91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PHASES = "'ready','submitting','monitoring','finalizing','uncertain','complete'"
_OUTCOMES = (
    "'armed','accepted','rejected','uncertain','reconciled_zero',"
    "'reconciled_one','reconciled_multiple'"
)


def upgrade() -> None:
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
        sa.Column("phase", sa.String(length=24), nullable=False),
        sa.Column("correlation", sa.String(length=128), nullable=False),
        sa.Column("attempt_no", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_token", sa.String(length=36), nullable=True),
        sa.Column("lease_generation", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uncertainty_code", sa.String(length=64), nullable=True),
        sa.Column("uncertainty_detail", sa.Text(), server_default="", nullable=False),
        sa.Column("observed_scheduler_state", sa.String(length=24), nullable=True),
        sa.Column("observed_exit_code", sa.Integer(), nullable=True),
        sa.Column("observed_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"phase IN ({_PHASES})", name="ck_execution_intent_phase"),
        sa.CheckConstraint("attempt_no >= 0", name="ck_execution_intent_attempt_no"),
        sa.CheckConstraint("lease_generation >= 0", name="ck_execution_intent_lease_generation"),
        sa.CheckConstraint(
            "((lease_owner IS NULL AND lease_token IS NULL AND lease_expires_at IS NULL) OR "
            "(lease_owner IS NOT NULL AND lease_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL))",
            name="ck_execution_intent_lease_tuple",
        ),
        sa.CheckConstraint(
            "((phase = 'complete' AND completed_at IS NOT NULL) OR "
            "(phase <> 'complete' AND completed_at IS NULL))",
            name="ck_execution_intent_completed",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("run_id"),
        sa.UniqueConstraint("correlation", name="uq_execution_intent_correlation"),
    )
    op.create_index(
        "ix_execution_intents_claimable",
        "run_execution_intents",
        ["next_attempt_at", "lease_expires_at", "created_at"],
        unique=False,
        sqlite_where=sa.text("completed_at IS NULL"),
        postgresql_where=sa.text("completed_at IS NULL"),
    )

    op.create_table(
        "run_submission_attempts",
        sa.Column("run_id", sa.String(length=40), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("correlation", sa.String(length=128), nullable=False),
        sa.Column("outcome", sa.String(length=24), nullable=False),
        sa.Column("scheduler_job_id", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("detail", sa.Text(), server_default="", nullable=False),
        sa.CheckConstraint("attempt_no > 0", name="ck_submission_attempt_no"),
        sa.CheckConstraint(f"outcome IN ({_OUTCOMES})", name="ck_submission_attempt_outcome"),
        sa.ForeignKeyConstraint(["run_id"], ["run_execution_intents.run_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("run_id", "attempt_no"),
    )
    op.create_index(
        "ix_submission_attempts_correlation",
        "run_submission_attempts",
        ["correlation", "attempt_no"],
        unique=False,
    )

    with op.batch_alter_table("artifacts", schema=None) as batch_op:
        batch_op.create_unique_constraint("uq_artifact_run_source_path", ["run_id", "source_path"])


def downgrade() -> None:
    with op.batch_alter_table("artifacts", schema=None) as batch_op:
        batch_op.drop_constraint("uq_artifact_run_source_path", type_="unique")

    op.drop_index("ix_submission_attempts_correlation", table_name="run_submission_attempts")
    op.drop_table("run_submission_attempts")
    op.drop_index("ix_execution_intents_claimable", table_name="run_execution_intents")
    op.drop_table("run_execution_intents")

    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_runs_finished_at", type_="check")
        batch_op.drop_constraint("ck_runs_running_has_job", type_="check")
        batch_op.drop_constraint("ck_runs_scheduler_link", type_="check")
        batch_op.drop_constraint("ck_runs_status", type_="check")
