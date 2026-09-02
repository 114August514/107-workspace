"""Index exact Environment consumers for availability notifications.

Run Snapshots retain the execution contract in JSON. This reference table makes availability
fan-out queryable without loading every historical snapshot into Python.

Revision ID: c60d9e5f17a1
Revises: f50a9b7c6d5e
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "c60d9e5f17a1"
down_revision: str | None = "f50a9b7c6d5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ID = sa.String(length=40)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _backfill_references() -> None:
    bind = op.get_bind()
    snapshots = sa.table(
        "run_snapshots",
        sa.column("id", _ID),
        sa.column("payload", sa.JSON()),
    )
    references = sa.table(
        "run_snapshot_environment_references",
        sa.column("snapshot_id", _ID),
        sa.column("environment_version_id", _ID),
    )
    values: set[tuple[str, str]] = set()
    rows = bind.execute(sa.select(snapshots.c.id, snapshots.c.payload)).mappings()
    for row in rows:
        environment = _mapping(_mapping(row["payload"]).get("environment"))
        version_id = environment.get("version_id")
        if isinstance(version_id, str):
            values.add((row["id"], version_id))
    if values:
        bind.execute(
            references.insert(),
            [
                {"snapshot_id": snapshot_id, "environment_version_id": version_id}
                for snapshot_id, version_id in values
            ],
        )


def upgrade() -> None:
    op.create_index("ix_projects_environment_version_id", "projects", ["environment_version_id"])
    op.create_index(
        "ix_run_configurations_environment_version_id",
        "run_configurations",
        ["environment_version_id"],
    )
    op.create_table(
        "run_snapshot_environment_references",
        sa.Column(
            "snapshot_id",
            _ID,
            sa.ForeignKey("run_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("environment_version_id", _ID, nullable=False),
        sa.PrimaryKeyConstraint("snapshot_id"),
    )
    op.create_index(
        "ix_run_snapshot_environment_ref_version",
        "run_snapshot_environment_references",
        ["environment_version_id"],
    )
    _backfill_references()


def downgrade() -> None:
    op.drop_index(
        "ix_run_snapshot_environment_ref_version",
        table_name="run_snapshot_environment_references",
    )
    op.drop_table("run_snapshot_environment_references")
    op.drop_index("ix_run_configurations_environment_version_id", table_name="run_configurations")
    op.drop_index("ix_projects_environment_version_id", table_name="projects")
