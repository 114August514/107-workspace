"""Add external identity mappings for authenticated providers.

Revision ID: e82a4c6d9f10
Revises: a7b8c9d0e1f2
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e82a4c6d9f10"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_identities",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_user_id", name="uq_external_identity_provider_user"
        ),
    )
    op.create_index("ix_external_identities_user_id", "external_identities", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_external_identities_user_id", table_name="external_identities")
    op.drop_table("external_identities")
