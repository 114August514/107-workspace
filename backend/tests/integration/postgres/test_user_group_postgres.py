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

PREVIOUS_REVISION = "a41b9c3e7d2f"
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
async def test_postgresql_workspace_cutover_roundtrip(tmp_path: Path) -> None:
    url = _url()
    os.environ["WORKSPACE107_DATABASE_URL"] = url
    get_settings.cache_clear()
    config = _alembic_config(url)
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("DROP SCHEMA public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
        await _migrate(config, PREVIOUS_REVISION)
        async with engine.begin() as connection:
            now = datetime(2026, 8, 17, tzinfo=UTC)
            await connection.execute(
                text(
                    "INSERT INTO users (id, username, display_name, email, created_at) "
                    "VALUES ('usr_alice', 'alice', 'Alice', NULL, :now)"
                ),
                {"now": now},
            )
            await connection.execute(
                text(
                    "INSERT INTO user_groups (id, name, description, created_by_id, created_at) "
                    "VALUES ('grp_lab', 'Research Lab', '', 'usr_alice', :now)"
                ),
                {"now": now},
            )
            await connection.execute(
                text(
                    "INSERT INTO memberships "
                    "(id, user_group_id, user_id, role, status, created_at) "
                    "VALUES ('mbr_alice', 'grp_lab', 'usr_alice', 'owner', 'active', :now)"
                ),
                {"now": now},
            )
            await connection.execute(
                text(
                    "INSERT INTO workspaces "
                    "(id, kind, name, description, owner_id, "
                    "default_environment_version_id, created_at) "
                    "VALUES ('ws_personal', 'personal', 'Alice personal', '', "
                    "'usr_alice', NULL, :now)"
                ),
                {"now": now},
            )
            await connection.execute(
                text(
                    "INSERT INTO projects "
                    "(id, workspace_id, owner_user_id, owner_user_group_id, name, description, "
                    "status, visibility, environment_version_id, default_run_configuration_id, "
                    "created_by, created_at, updated_at) "
                    "VALUES ('prj_personal', 'ws_personal', 'usr_alice', NULL, 'Discard me', '', "
                    "'active', 'owner_scope', NULL, NULL, 'usr_alice', :now, :now)"
                ),
                {"now": now},
            )

        await _migrate(config, "head")
        assert await _rows(
            engine,
            "SELECT to_regclass('public.workspaces'), "
            "to_regclass('public.legacy_personal_memberships'), "
            "to_regclass('public.user_group_migration_provenance')",
        ) == [(None, None, None)]
        assert await _rows(engine, "SELECT id FROM projects") == []
        assert await _rows(engine, "SELECT id, created_by_id FROM user_groups") == [
            ("grp_lab", "usr_alice")
        ]
        assert await _rows(
            engine,
            "SELECT user_group_id, user_id, role, status FROM memberships",
        ) == [("grp_lab", "usr_alice", "owner", "active")]
        assert (
            await _rows(
                engine,
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='projects' "
                "AND column_name='workspace_id'",
            )
            == []
        )

        await _migrate(config, PREVIOUS_REVISION, downgrade=True)
        assert await _rows(
            engine,
            "SELECT to_regclass('public.workspaces'), "
            "to_regclass('public.legacy_personal_memberships'), "
            "to_regclass('public.user_group_migration_provenance')",
        ) == [
            (
                "workspaces",
                "legacy_personal_memberships",
                "user_group_migration_provenance",
            )
        ]
        assert await _rows(engine, "SELECT id FROM projects") == []
        assert await _rows(engine, "SELECT id FROM workspaces") == []

        await _migrate(config, "head")
        assert await _rows(engine, "SELECT to_regclass('public.workspaces')") == [(None,)]
        assert await _rows(engine, "SELECT id FROM user_groups") == [("grp_lab",)]
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
        run_sync_interval_seconds=0,
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
                    "SELECT user_id, role, status FROM memberships "
                    "WHERE user_group_id = :group_id ORDER BY user_id"
                ),
                {"group_id": group_id},
            )
            persisted = list(rows.fetchall())
        owners = [row for row in persisted if row[1] == "owner" and row[2] == "active"]
        assert len(owners) == 1
        owner_id = owners[0][0]
        if winner == "transfer":
            assert owner_id == bob.id
            assert next(row for row in persisted if row[0] == alice.id)[1:] == (
                "admin",
                "active",
            )
            assert next(row for row in persisted if row[0] == bob.id)[1:3] == ("owner", "active")
        else:
            assert owner_id == alice.id
            assert next(row for row in persisted if row[0] == bob.id)[2] == "removed"
    finally:
        await context.engine.dispose()
