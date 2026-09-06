from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from sqlalchemy import text

from workspace107.api.deps import build_services
from workspace107.config import Settings, get_settings
from workspace107.domain.errors import ConflictError, ObjectNotFound, PermissionDenied
from workspace107.main import build_context

pytestmark = pytest.mark.skipif(
    not os.environ.get("WORKSPACE107_TEST_POSTGRESQL_URL"),
    reason="WORKSPACE107_TEST_POSTGRESQL_URL is required for PostgreSQL evidence",
)


def _url() -> str:
    value = os.environ.get("WORKSPACE107_TEST_POSTGRESQL_URL")
    if not value:
        pytest.fail("WORKSPACE107_TEST_POSTGRESQL_URL is required for PostgreSQL evidence tests")
    return value


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
