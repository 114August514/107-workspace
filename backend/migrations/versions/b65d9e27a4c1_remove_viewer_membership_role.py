"""Remove Viewer from Membership roles without granting additional access.

The canonical Membership roles after this revision are Owner, Admin, and Member.
Existing Viewer rows are converted to removed Member rows. This preserves the
membership record while revoking access; silently promoting Viewer to active Member
would increase privileges. Downgrade cannot reconstruct the removed Viewer role.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b65d9e27a4c1"
down_revision: str | None = "c471ac39f002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE memberships SET role='member', status='removed' WHERE role='viewer'")
    )


def downgrade() -> None:
    # Viewer was intentionally removed from the product model. There is no truthful
    # way to distinguish rows that used to be Viewer after upgrade, so do not invent it.
    pass
