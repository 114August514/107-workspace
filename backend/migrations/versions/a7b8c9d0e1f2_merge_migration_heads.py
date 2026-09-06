"""Merge the concurrent migration heads from Issues #54 and #49.

Revision ID: a7b8c9d0e1f2
Revises: b3d8e2a64c19, e8a1c4d2f6b9
Create Date: 2026-09-04
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "a7b8c9d0e1f2"
down_revision: tuple[str, str] = ("b3d8e2a64c19", "e8a1c4d2f6b9")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the two already-applied schema branches."""


def downgrade() -> None:
    """Separate the branches again when rolling back the merge point."""
