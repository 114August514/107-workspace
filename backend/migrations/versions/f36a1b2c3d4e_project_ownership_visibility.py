"""Give Project an explicit User/User Group owner and visibility."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f36a1b2c3d4e"
down_revision: str | None = "e35a1d7c9b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("owner_user_id", sa.String(40), nullable=True))
    op.add_column("projects", sa.Column("owner_user_group_id", sa.String(40), nullable=True))
    op.add_column(
        "projects",
        sa.Column("visibility", sa.String(32), nullable=False, server_default="owner_scope"),
    )
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT p.id, p.workspace_id, w.kind, w.owner_id "
            "FROM projects p JOIN workspaces w ON w.id = p.workspace_id"
        )
    ).mappings()
    for row in rows:
        if row["kind"] == "personal":
            bind.execute(
                sa.text("UPDATE projects SET owner_user_id = :owner WHERE id = :id"),
                {"owner": row["owner_id"], "id": row["id"]},
            )
        else:
            bind.execute(
                sa.text("UPDATE projects SET owner_user_group_id = :owner WHERE id = :id"),
                {"owner": row["workspace_id"], "id": row["id"]},
            )
    op.create_index("ix_projects_owner_user_id", "projects", ["owner_user_id"])
    op.create_index("ix_projects_owner_user_group_id", "projects", ["owner_user_group_id"])
    # Keep the old workspace anchor during the bounded #37-#42 migration window.
    with op.batch_alter_table("projects") as batch:
        batch.create_foreign_key(
            "fk_projects_owner_user_id_users",
            "users",
            ["owner_user_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_projects_owner_user_group_id_user_groups",
            "user_groups",
            ["owner_user_group_id"],
            ["id"],
        )
        batch.create_check_constraint(
            "ck_projects_exactly_one_owner",
            "((owner_user_id IS NOT NULL AND owner_user_group_id IS NULL) "
            "OR (owner_user_id IS NULL AND owner_user_group_id IS NOT NULL))",
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("ck_projects_exactly_one_owner", type_="check")
        batch.drop_constraint("fk_projects_owner_user_group_id_user_groups", type_="foreignkey")
        batch.drop_constraint("fk_projects_owner_user_id_users", type_="foreignkey")
    op.drop_index("ix_projects_owner_user_group_id", table_name="projects")
    op.drop_index("ix_projects_owner_user_id", table_name="projects")
    op.drop_column("projects", "visibility")
    op.drop_column("projects", "owner_user_group_id")
    op.drop_column("projects", "owner_user_id")
