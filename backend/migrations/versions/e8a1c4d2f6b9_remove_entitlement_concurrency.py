"""Remove the product-side Resource Entitlement concurrency quota.

Revision ID: e8a1c4d2f6b9
Revises: b3d8e2a64c19
Create Date: 2026-09-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8a1c4d2f6b9"
down_revision: str | None = "b3d8e2a64c19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("resource_entitlements", schema=None) as batch_op:
        batch_op.drop_column("max_concurrent_runs")


def downgrade() -> None:
    with op.batch_alter_table("resource_entitlements", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "max_concurrent_runs",
                sa.Integer(),
                server_default=sa.text("1"),
                nullable=False,
            )
        )
    with op.batch_alter_table("resource_entitlements", schema=None) as batch_op:
        batch_op.alter_column("max_concurrent_runs", server_default=None)
