"""Add grants table for cross-owner USE grants (Issue #40).

Grants separate asset ownership from use entitlement: a Grantor (User or User
Group) issues a USE grant to a Grantee (User or User Group), allowing the
grantee to reference the Grantor's top-level Environment or Shared Resource
from their own Project. Target can also be ALL to cover all current and future
assets owned by the Grantor.

The grants table stores grantor and grantee as discriminated unions
(kind + id columns) and does not FK to environments/shared_resources, so a
grant row can outlive a deleted asset until the application layer cleans it up.

Revision ID: 1f61cd1dc3ac
Revises: f37c0a1e2b9d
Create Date: 2026-08-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1f61cd1dc3ac"
down_revision: str | None = "f37c0a1e2b9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ID = sa.String(length=40)


def upgrade() -> None:
    op.create_table(
        "grants",
        sa.Column("id", _ID, primary_key=True),
        sa.Column("grantor_kind", sa.String(length=16), nullable=False),
        sa.Column("grantor_id", _ID, nullable=False),
        sa.Column("grantee_kind", sa.String(length=16), nullable=False),
        sa.Column("grantee_id", _ID, nullable=False),
        sa.Column("target_kind", sa.String(length=32), nullable=False),
        sa.Column("target_id", _ID, nullable=False, server_default=""),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column(
            "granted_by_id",
            _ID,
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "grantor_kind",
            "grantor_id",
            "grantee_kind",
            "grantee_id",
            "target_kind",
            "target_id",
            "action",
            name="uq_grant_grantor_grantee_target_action",
        ),
    )
    op.create_index("ix_grants_target", "grants", ["target_kind", "target_id"], unique=False)
    op.create_index("ix_grants_grantee", "grants", ["grantee_kind", "grantee_id"], unique=False)
    op.create_index("ix_grants_grantor", "grants", ["grantor_kind", "grantor_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_grants_grantor", table_name="grants")
    op.drop_index("ix_grants_grantee", table_name="grants")
    op.drop_index("ix_grants_target", table_name="grants")
    op.drop_table("grants")
