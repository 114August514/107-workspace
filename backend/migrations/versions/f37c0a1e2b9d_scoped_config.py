"""Migrate Workspace config rows to explicit User/UserGroup/Project scopes."""

import copy
import json
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f37c0a1e2b9d"
down_revision: str | None = "e35a1d7c9b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _scope_for_workspace(bind: sa.Connection, workspace_id: str) -> tuple[str, str]:
    row = (
        bind.execute(
            sa.text("SELECT kind, owner_id FROM workspaces WHERE id=:id"), {"id": workspace_id}
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise RuntimeError(f"orphan Workspace config: {workspace_id}")
    if row["kind"] == "personal":
        anchors = bind.execute(
            sa.text("SELECT COUNT(*) FROM workspaces WHERE kind='personal' AND owner_id=:id"),
            {"id": row["owner_id"]},
        ).scalar_one()
        user = bind.execute(
            sa.text("SELECT 1 FROM users WHERE id=:id"), {"id": row["owner_id"]}
        ).first()
        if anchors != 1 or user is None:
            raise RuntimeError(f"personal Workspace owner/anchor is not provable: {workspace_id}")
        return "user", row["owner_id"]
    if row["kind"] == "collaborative":
        group = bind.execute(
            sa.text("SELECT 1 FROM user_groups WHERE id=:id"), {"id": workspace_id}
        ).first()
        owner = bind.execute(
            sa.text(
                "SELECT 1 FROM memberships "
                "WHERE user_group_id=:id AND role='owner' AND status='active'"
            ),
            {"id": workspace_id},
        ).first()
        if group is None or owner is None:
            raise RuntimeError(
                f"collaborative Workspace group/active owner is not provable: {workspace_id}"
            )
        return "user_group", workspace_id
    raise RuntimeError(f"unprovable Workspace kind: {workspace_id}: {row['kind']}")


def _preflight_config_rows(bind: sa.Connection, *, allow_project: bool = False) -> None:
    valid = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    for table in ("workspace_variables", "workspace_secrets"):
        if not sa.inspect(bind).has_table(table):
            continue
        for row in bind.execute(sa.text(f"SELECT workspace_id, name FROM {table}")).mappings():
            if not valid.fullmatch(row["name"]):
                raise RuntimeError(f"invalid legacy config name: {row['name']!r}")
            _scope_for_workspace(bind, row["workspace_id"])
    for table in ("variables", "secrets"):
        if not sa.inspect(bind).has_table(table):
            continue
        for row in bind.execute(
            sa.text(f"SELECT scope_kind, scope_id, name FROM {table}")
        ).mappings():
            if not valid.fullmatch(row["name"]):
                raise RuntimeError(f"invalid scoped config name: {row['name']!r}")
            if row["scope_kind"] == "project" and allow_project:
                continue
            if row["scope_kind"] not in ("user", "user_group"):
                raise RuntimeError(f"unknown or non-legacy scope: {row['scope_kind']}")
            if row["scope_kind"] == "user":
                statement = sa.text(
                    "SELECT id FROM workspaces WHERE kind='personal' AND owner_id=:scope_id"
                )
            else:
                statement = sa.text(
                    "SELECT id FROM workspaces WHERE kind='collaborative' AND id=:scope_id"
                )
            matches = bind.execute(statement, {"scope_id": row["scope_id"]}).scalars().all()
            if len(matches) != 1:
                raise RuntimeError(
                    f"cannot prove legacy scope mapping: {row['scope_kind']}:{row['scope_id']}"
                )


def _snapshot_rows(bind: sa.Connection) -> list[dict[str, object]]:
    return bind.execute(sa.text("SELECT id, payload FROM run_snapshots")).mappings().all()


def _payload(value: object) -> dict[str, object]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise RuntimeError("Run Snapshot payload is not an object")
    return copy.deepcopy(value)


def _project_workspace(bind: sa.Connection, project_id: str) -> str:
    row = bind.execute(
        sa.text("SELECT workspace_id FROM projects WHERE id=:id"), {"id": project_id}
    ).scalar_one_or_none()
    if row is None:
        raise RuntimeError(f"Run Snapshot Project is missing: {project_id}")
    return row


def _migrate_snapshot_refs(bind: sa.Connection, *, downgrade: bool) -> None:
    updates: list[tuple[object, dict[str, object]]] = []
    for row in _snapshot_rows(bind):
        payload = _payload(row["payload"])
        env = payload.get("env")
        if not isinstance(env, dict):
            raise RuntimeError(f"Run Snapshot {row['id']} env is malformed")
        refs = env.get("secret_refs", {})
        if not isinstance(refs, dict):
            raise RuntimeError(f"Run Snapshot {row['id']} secret_refs is malformed")
        workspace_id = _project_workspace(bind, str(payload.get("project_id", "")))
        owner_kind, owner_id = _scope_for_workspace(bind, workspace_id)
        migrated: dict[str, str] = {}
        for env_name, raw in refs.items():
            if not isinstance(env_name, str) or not env_name or not isinstance(raw, str):
                raise RuntimeError(f"Run Snapshot {row['id']} Secret reference is malformed")
            parts = raw.split(":")
            if downgrade:
                if (
                    len(parts) != 3
                    or (parts[0], parts[1]) != (owner_kind, owner_id)
                    or not parts[2]
                ):
                    raise RuntimeError(
                        f"Run Snapshot {row['id']} Secret reference is not legacy-representable"
                    )
                migrated[env_name] = parts[2]
            elif len(parts) == 1:
                migrated[env_name] = f"{owner_kind}:{owner_id}:{raw}"
            elif len(parts) == 3 and (parts[0], parts[1]) == (owner_kind, owner_id) and all(parts):
                migrated[env_name] = raw
            else:
                raise RuntimeError(f"Run Snapshot {row['id']} Secret reference is not owner-scoped")
        env["secret_refs"] = migrated
        payload["env"] = env
        updates.append((row["id"], payload))
    statement = sa.text("UPDATE run_snapshots SET payload=:payload WHERE id=:id").bindparams(
        sa.bindparam("payload", type_=sa.JSON())
    )
    for snapshot_id, payload in updates:
        bind.execute(statement, {"id": snapshot_id, "payload": payload})


def _create_scoped_tables() -> None:
    op.create_table(
        "variables",
        sa.Column("scope_kind", sa.String(32), nullable=False),
        sa.Column("scope_id", sa.String(40), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("scope_kind", "scope_id", "name"),
    )
    op.create_table(
        "secrets",
        sa.Column("scope_kind", sa.String(32), nullable=False),
        sa.Column("scope_id", sa.String(40), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("scope_kind", "scope_id", "name"),
    )


def upgrade() -> None:
    bind = op.get_bind()
    _preflight_config_rows(bind)
    _migrate_snapshot_refs(bind, downgrade=False)
    _create_scoped_tables()
    for source, target in (("workspace_variables", "variables"), ("workspace_secrets", "secrets")):
        for row in bind.execute(sa.text(f"SELECT * FROM {source}")).mappings().all():
            kind, scope_id = _scope_for_workspace(bind, row["workspace_id"])
            columns = "scope_kind,scope_id,name,value" + (
                ",updated_at" if target == "secrets" else ""
            )
            values = ":kind,:scope_id,:name,:value" + (
                ",:updated_at" if target == "secrets" else ""
            )
            bind.execute(
                sa.text(f"INSERT INTO {target} ({columns}) VALUES ({values})"),
                {
                    "kind": kind,
                    "scope_id": scope_id,
                    "name": row["name"],
                    "value": row["value"],
                    "updated_at": row.get("updated_at"),
                },
            )
    op.drop_table("workspace_variables")
    op.drop_table("workspace_secrets")


def downgrade() -> None:
    bind = op.get_bind()
    _preflight_config_rows(bind, allow_project=True)
    if (
        bind.execute(sa.text("SELECT 1 FROM variables WHERE scope_kind='project' LIMIT 1")).first()
        or bind.execute(sa.text("SELECT 1 FROM secrets WHERE scope_kind='project' LIMIT 1")).first()
    ):
        raise RuntimeError("cannot downgrade Project-scoped config to Workspace scope")
    _migrate_snapshot_refs(bind, downgrade=True)
    op.create_table(
        "workspace_variables",
        sa.Column("workspace_id", sa.String(40), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("workspace_id", "name"),
    )
    op.create_table(
        "workspace_secrets",
        sa.Column("workspace_id", sa.String(40), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("workspace_id", "name"),
    )
    for source, target in (("variables", "workspace_variables"), ("secrets", "workspace_secrets")):
        for row in bind.execute(sa.text(f"SELECT * FROM {source}")).mappings().all():
            if row["scope_kind"] == "user":
                stmt = sa.text("SELECT id FROM workspaces WHERE kind='personal' AND owner_id=:id")
            elif row["scope_kind"] == "user_group":
                stmt = sa.text("SELECT id FROM workspaces WHERE kind='collaborative' AND id=:id")
            else:
                raise RuntimeError(f"unknown or non-legacy scope: {row['scope_kind']}")
            workspace = bind.execute(stmt, {"id": row["scope_id"]}).scalars().all()
            if len(workspace) != 1:
                raise RuntimeError(
                    f"cannot reverse scoped config {row['scope_kind']}:{row['scope_id']}"
                )
            columns = "workspace_id,name,value" + (
                ",updated_at" if target == "workspace_secrets" else ""
            )
            values = ":workspace_id,:name,:value" + (
                ",:updated_at" if target == "workspace_secrets" else ""
            )
            bind.execute(
                sa.text(f"INSERT INTO {target} ({columns}) VALUES ({values})"),
                {
                    "workspace_id": workspace[0],
                    "name": row["name"],
                    "value": row["value"],
                    "updated_at": row.get("updated_at"),
                },
            )
    op.drop_table("variables")
    op.drop_table("secrets")
