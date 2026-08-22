"""Add grants table for cross-owner USE grants (Issue #40).

Grants separate asset ownership from use entitlement: an asset Owner can issue a
USE grant to another User or User Group, allowing that grantee to reference the
asset (top-level Environment or Shared Resource) from their own Project.

The grants table stores grantee as a discriminated union (grantee_kind +
grantee_id) and does not FK to environments/shared_resources, so a grant row can
outlive a deleted asset until the application layer cleans it up.

Revision ID: 1f61cd1dc3ac
Revises: c471ac39f002
Create Date: 2026-08-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1f61cd1dc3ac"
down_revision: str | None = "c471ac39f002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ID = sa.String(length=40)


def upgrade() -> None:
    op.create_table(
        "grants",
        sa.Column("id", _ID, primary_key=True),
        sa.Column("grantee_kind", sa.String(length=16), nullable=False),
        sa.Column("grantee_id", _ID, nullable=False),
        sa.Column("target_kind", sa.String(length=32), nullable=False),
        sa.Column("target_id", _ID, nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column(
            "granted_by_id",
            _ID,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("grantor_owner_kind", sa.String(length=16), nullable=False),
        sa.Column("grantor_owner_id", _ID, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "grantee_kind",
            "grantee_id",
            "target_kind",
            "target_id",
            "action",
            name="uq_grant_grantee_target_action",
        ),
    )
    op.create_index("ix_grants_target", "grants", ["target_kind", "target_id"], unique=False)
    op.create_index("ix_grants_grantee", "grants", ["grantee_kind", "grantee_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_grants_grantee", table_name="grants")
    op.drop_index("ix_grants_target", table_name="grants")
    op.drop_table("grants")
