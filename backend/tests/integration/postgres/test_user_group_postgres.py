from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from workspace107.api.deps import build_services
from workspace107.config import Settings, get_settings
from workspace107.domain.errors import ConflictError, ObjectNotFound, PermissionDenied
from workspace107.main import build_context

PREVIOUS_REVISION = "a3f7c2e91b84"
TARGET_REVISION = "a41b9c3e7d2f"
pytestmark = pytest.mark.skipif(
    not os.environ.get("WORKSPACE107_TEST_POSTGRESQL_URL"),
    reason="WORKSPACE107_TEST_POSTGRESQL_URL is required for PostgreSQL evidence",
)


def _url() -> str:
    value = os.environ.get("WORKSPACE107_TEST_POSTGRESQL_URL")
    if not value:
        pytest.fail("WORKSPACE107_TEST_POSTGRESQL_URL is required for PostgreSQL evidence tests")
    return value


def _alembic_config(url: str) -> Config:
    backend = Path(__file__).resolve().parents[3]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


async def _migrate(config: Config, revision: str, *, downgrade: bool = False) -> None:
    operation = command.downgrade if downgrade else command.upgrade
    await asyncio.to_thread(operation, config, revision)


async def _rows(engine: AsyncEngine, query: str) -> list[tuple[object, ...]]:
    async with engine.connect() as connection:
        result = await connection.execute(text(query))
        return list(result.fetchall())


@pytest.mark.asyncio
async def test_postgresql_legacy_migration_roundtrip(tmp_path: Path) -> None:
    url = _url()
    os.environ["WORKSPACE107_DATABASE_URL"] = url
    get_settings.cache_clear()
    config = _alembic_config(url)
    engine = create_async_engine(url)
    try:
        await _migrate(config, PREVIOUS_REVISION)
        async with engine.begin() as connection:
            now = datetime(2026, 8, 17, tzinfo=UTC)
            await connection.execute(
                text(
                    "INSERT INTO users (id, username, display_name, email, created_at) "
                    "VALUES (:id, :username, :display_name, NULL, :created_at)"
                ),
                [
                    {
                        "id": "usr_alice",
                        "username": "alice",
                        "display_name": "Alice",
                        "created_at": now,
                    },
                    {"id": "usr_bob", "username": "bob", "display_name": "Bob", "created_at": now},
                    {
                        "id": "usr_carol",
                        "username": "carol",
                        "display_name": "Carol",
                        "created_at": now,
                    },
                ],
            )
            await connection.execute(
                text(
                    "INSERT INTO workspaces "
                    "(id, kind, name, description, owner_id, "
                    "default_environment_version_id, created_at) "
                    "VALUES (:id, :kind, :name, :description, :owner_id, NULL, :created_at)"
                ),
                [
                    {
                        "id": "ws_personal",
                        "kind": "personal",
                        "name": "Alice personal",
                        "description": "keep",
                        "owner_id": "usr_alice",
                        "created_at": now,
                    },
                    {
                        "id": "ws_collab",
                        "kind": "collaborative",
                        "name": "Research Lab",
                        "description": "migrate",
                        "owner_id": "usr_alice",
                        "created_at": now,
                    },
                ],
            )
            await connection.execute(
                text(
                    "INSERT INTO memberships "
                    "(id, workspace_id, user_id, role, status, created_at) "
                    "VALUES (:id, :workspace_id, :user_id, :role, :status, :created_at)"
                ),
                [
                    {
                        "id": "mbr_personal",
                        "workspace_id": "ws_personal",
                        "user_id": "usr_alice",
                        "role": "owner",
                        "status": "active",
                        "created_at": now,
                    },
                    {
                        "id": "mbr_alice",
                        "workspace_id": "ws_collab",
                        "user_id": "usr_alice",
                        "role": "member",
                        "status": "left",
                        "created_at": now,
                    },
                    {
                        "id": "mbr_bob",
                        "workspace_id": "ws_collab",
                        "user_id": "usr_bob",
                        "role": "owner",
                        "status": "active",
                        "created_at": now,
                    },
                ],
            )
            await connection.execute(
                text(
                    "INSERT INTO projects "
                    "(id, workspace_id, name, description, status, environment_version_id, "
                    "default_run_configuration_id, created_by, created_at, updated_at) "
                    "VALUES ('prj_personal', 'ws_personal', 'Keep me', '', 'active', "
                    "NULL, NULL, 'usr_alice', :now, :now)"
                ),
                {"now": now},
            )
        await _migrate(config, TARGET_REVISION)
        assert await _rows(engine, "SELECT id FROM user_groups ORDER BY id") == [("ws_collab",)]
        assert await _rows(
            engine, "SELECT created_by_id FROM user_groups WHERE id='ws_collab'"
        ) == [(None,)]
        assert await _rows(
            engine,
            "SELECT user_id, role, status FROM memberships "
            "WHERE user_group_id='ws_collab' ORDER BY user_id",
        ) == [("usr_alice", "owner", "active"), ("usr_bob", "admin", "active")]
        assert await _rows(engine, "SELECT id FROM legacy_personal_memberships") == [
            ("mbr_personal",)
        ]
        assert await _rows(engine, "SELECT id, workspace_id FROM projects") == [
            ("prj_personal", "ws_personal")
        ]
        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE user_groups SET name='Renamed Lab' WHERE id='ws_collab'")
            )
            await connection.execute(
                text(
                    "UPDATE memberships SET role='admin' "
                    "WHERE user_group_id='ws_collab' AND user_id='usr_alice'"
                )
            )
            await connection.execute(
                text(
                    "UPDATE memberships SET role='owner' "
                    "WHERE user_group_id='ws_collab' AND user_id='usr_bob'"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO workspaces "
                    "(id, kind, name, description, owner_id, "
                    "default_environment_version_id, created_at) "
                    "VALUES ('grp_new', 'collaborative', 'New Group', '', 'usr_bob', "
                    "NULL, '2026-08-17 00:00:00+00:00')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO user_groups "
                    "(id, name, description, created_by_id, created_at) "
                    "VALUES ('grp_new', 'New Group', '', 'usr_carol', "
                    "'2026-08-17 00:00:00+00:00')"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO memberships "
                    "(id, user_group_id, user_id, role, status, created_at) "
                    "VALUES ('mbr_new_carol', 'grp_new', 'usr_carol', 'admin', "
                    "'active', '2026-08-17 00:00:00+00:00'), "
                    "('mbr_new_bob', 'grp_new', 'usr_bob', 'owner', 'active', "
                    "'2026-08-17 00:00:00+00:00')"
                )
            )
        await _migrate(config, PREVIOUS_REVISION, downgrade=True)
        assert await _rows(
            engine,
            "SELECT id, name, owner_id FROM workspaces WHERE kind='collaborative' ORDER BY id",
        ) == [("grp_new", "New Group", "usr_bob"), ("ws_collab", "Renamed Lab", "usr_bob")]
        assert await _rows(
            engine,
            "SELECT workspace_id, user_id, role, status FROM memberships "
            "ORDER BY workspace_id, user_id",
        ) == [
            ("grp_new", "usr_bob", "owner", "active"),
            ("grp_new", "usr_carol", "admin", "active"),
            ("ws_collab", "usr_alice", "admin", "active"),
            ("ws_collab", "usr_bob", "owner", "active"),
            ("ws_personal", "usr_alice", "owner", "active"),
        ]
        await _migrate(config, TARGET_REVISION)
        assert await _rows(engine, "SELECT id, created_by_id FROM user_groups ORDER BY id") == [
            ("grp_new", "usr_carol"),
            ("ws_collab", None),
        ]
        assert await _rows(engine, "SELECT id, workspace_id FROM projects") == [
            ("prj_personal", "ws_personal")
        ]
        assert await _rows(engine, "SELECT id FROM legacy_personal_memberships") == [
            ("mbr_personal",)
        ]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_postgresql_owner_race_serializes_transfer_and_removal(tmp_path: Path) -> None:
    url = _url()
    os.environ["WORKSPACE107_DATABASE_URL"] = url
    get_settings.cache_clear()
    settings = Settings(
        database_url=url,
        storage_root=tmp_path / "storage",
    )
    context = build_context(settings)
    try:
        async with context.session_factory() as session:
            services = build_services(context, session)
            alice = await services.identity.ensure_user("race_alice", "Race Alice")
            bob = await services.identity.ensure_user("race_bob", "Race Bob")
            group = await services.user_groups.create(alice.id, "Race Group")
            await services.user_groups.invite_member(alice.id, group.user_group.id, bob.username)
            await services.user_groups.respond_to_invitation(
                bob.id, group.user_group.id, accept=True
            )
            await session.commit()
            group_id = group.user_group.id

        barrier = asyncio.Barrier(2)

        async def run_transfer() -> str:
            async with context.session_factory() as session:
                services = build_services(context, session)
                await barrier.wait()
                try:
                    await services.user_groups.transfer_ownership(alice.id, group_id, bob.id)
                    await session.commit()
                    return "transfer"
                except Exception:
                    await session.rollback()
                    raise

        async def run_remove() -> str:
            async with context.session_factory() as session:
                services = build_services(context, session)
                await barrier.wait()
                try:
                    await services.user_groups.remove_member(alice.id, group_id, bob.id)
                    await session.commit()
                    return "remove"
                except Exception:
                    await session.rollback()
                    raise

        results = await asyncio.gather(run_transfer(), run_remove(), return_exceptions=True)
        successes = [result for result in results if isinstance(result, str)]
        failures = [result for result in results if isinstance(result, Exception)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], (ConflictError, PermissionDenied, ObjectNotFound))
        winner = successes[0]

        async with context.session_factory() as session:
            rows = await session.execute(
                text(
                    "SELECT m.user_id, m.role, m.status, w.owner_id "
                    "FROM memberships AS m JOIN workspaces AS w ON w.id = m.user_group_id "
                    "WHERE m.user_group_id = :group_id ORDER BY m.user_id"
                ),
                {"group_id": group_id},
            )
            persisted = list(rows.fetchall())
        owners = [row for row in persisted if row[1] == "owner" and row[2] == "active"]
        assert len(owners) == 1
        owner_id = owners[0][0]
        assert owners[0][3] == owner_id
        if winner == "transfer":
            assert owner_id == bob.id
            assert next(row for row in persisted if row[0] == alice.id)[1:] == (
                "admin",
                "active",
                bob.id,
            )
            assert next(row for row in persisted if row[0] == bob.id)[1:3] == ("owner", "active")
        else:
            assert owner_id == alice.id
            assert next(row for row in persisted if row[0] == bob.id)[2] == "removed"
    finally:
        await context.engine.dispose()
