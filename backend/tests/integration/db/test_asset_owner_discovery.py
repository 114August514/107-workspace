from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from workspace107.domain.enums import MembershipRole, MembershipStatus
from workspace107.domain.ownership import OwnerKind, OwnerReference
from workspace107.infrastructure.db import tables as t
from workspace107.infrastructure.db.repositories import SqlRepositories

ALICE_ID = "usr_asset_alice"
BOB_ID = "usr_asset_bob"
ACTIVE_GROUP_ID = "grp_asset_active"
INVITED_GROUP_ID = "grp_asset_invited"
LEFT_GROUP_ID = "grp_asset_left"
OTHER_GROUP_ID = "grp_asset_other"
REMOVED_GROUP_ID = "grp_asset_removed"


@pytest.fixture
async def session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'asset-discovery.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(t.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as scoped_session:
        yield scoped_session
    await engine.dispose()


async def _seed_owners(session: AsyncSession) -> None:
    now = datetime(2026, 8, 18, 17, 7, tzinfo=UTC)
    session.add_all(
        [
            t.UserRow(
                id=ALICE_ID,
                username="asset-alice",
                display_name="Asset Alice",
                email=None,
                created_at=now,
            ),
            t.UserRow(
                id=BOB_ID,
                username="asset-bob",
                display_name="Asset Bob",
                email=None,
                created_at=now,
            ),
        ]
    )
    await session.flush()

    session.add_all(
        [
            t.UserGroupRow(
                id=group_id,
                name=group_id,
                description="",
                created_by_id=BOB_ID,
                created_at=now,
            )
            for group_id in (
                ACTIVE_GROUP_ID,
                INVITED_GROUP_ID,
                LEFT_GROUP_ID,
                REMOVED_GROUP_ID,
                OTHER_GROUP_ID,
            )
        ]
    )
    await session.flush()

    memberships = []
    for group_id in (
        ACTIVE_GROUP_ID,
        INVITED_GROUP_ID,
        LEFT_GROUP_ID,
        REMOVED_GROUP_ID,
        OTHER_GROUP_ID,
    ):
        memberships.append(
            t.MembershipRow(
                id=f"mbr_owner_{group_id.removeprefix('grp_asset_')}",
                user_group_id=group_id,
                user_id=BOB_ID,
                role=MembershipRole.OWNER.value,
                status=MembershipStatus.ACTIVE.value,
                created_at=now,
            )
        )
    memberships.extend(
        [
            t.MembershipRow(
                id="mbr_asset_alice_active",
                user_group_id=ACTIVE_GROUP_ID,
                user_id=ALICE_ID,
                role=MembershipRole.MEMBER.value,
                status=MembershipStatus.ACTIVE.value,
                created_at=now,
            ),
            t.MembershipRow(
                id="mbr_asset_alice_invited",
                user_group_id=INVITED_GROUP_ID,
                user_id=ALICE_ID,
                role=MembershipRole.MEMBER.value,
                status=MembershipStatus.INVITED.value,
                created_at=now,
            ),
            t.MembershipRow(
                id="mbr_asset_alice_left",
                user_group_id=LEFT_GROUP_ID,
                user_id=ALICE_ID,
                role=MembershipRole.MEMBER.value,
                status=MembershipStatus.LEFT.value,
                created_at=now,
            ),
            t.MembershipRow(
                id="mbr_asset_alice_removed",
                user_group_id=REMOVED_GROUP_ID,
                user_id=ALICE_ID,
                role=MembershipRole.MEMBER.value,
                status=MembershipStatus.REMOVED.value,
                created_at=now,
            ),
        ]
    )
    session.add_all(memberships)
    await session.flush()

    environment_specs = (
        ("env_owned_by_alice", ALICE_ID, None),
        ("env_owned_by_bob", BOB_ID, None),
        ("env_owned_by_active_group", None, ACTIVE_GROUP_ID),
        ("env_owned_by_invited_group", None, INVITED_GROUP_ID),
        ("env_owned_by_left_group", None, LEFT_GROUP_ID),
        ("env_owned_by_other_group", None, OTHER_GROUP_ID),
        ("env_owned_by_removed_group", None, REMOVED_GROUP_ID),
    )
    session.add_all(
        [
            t.EnvironmentRow(
                id=asset_id,
                name=asset_id,
                description="",
                owner_user_id=owner_user_id,
                owner_user_group_id=owner_group_id,
            )
            for asset_id, owner_user_id, owner_group_id in environment_specs
        ]
    )

    resource_specs = (
        ("shr_owned_by_alice", ALICE_ID, None),
        ("shr_owned_by_bob", BOB_ID, None),
        ("shr_owned_by_active_group", None, ACTIVE_GROUP_ID),
        ("shr_owned_by_invited_group", None, INVITED_GROUP_ID),
        ("shr_owned_by_left_group", None, LEFT_GROUP_ID),
        ("shr_owned_by_other_group", None, OTHER_GROUP_ID),
        ("shr_owned_by_removed_group", None, REMOVED_GROUP_ID),
    )
    session.add_all(
        [
            t.SharedResourceRow(
                id=asset_id,
                name=asset_id,
                description="",
                owner_user_id=owner_user_id,
                owner_user_group_id=owner_group_id,
                created_at=now,
            )
            for asset_id, owner_user_id, owner_group_id in resource_specs
        ]
    )
    await session.flush()

    session.add_all(
        [
            t.EnvironmentVersionRow(
                id="ev_visible_active_group",
                environment_id="env_owned_by_active_group",
                version="1",
                description="",
                image="visible:image",
                setup_command="",
                available=True,
            ),
            t.EnvironmentVersionRow(
                id="ev_hidden_bob",
                environment_id="env_owned_by_bob",
                version="1",
                description="",
                image="hidden:image",
                setup_command="",
                available=True,
            ),
            t.SharedResourceVersionRow(
                id="shrv_visible_active_group",
                shared_resource_id="shr_owned_by_active_group",
                sequence=1,
                description="",
                manifest_hash="1" * 64,
                validation_summary="测试夹具已校验",
                created_by=BOB_ID,
                created_at=now,
            ),
            t.SharedResourceVersionRow(
                id="shrv_hidden_bob",
                shared_resource_id="shr_owned_by_bob",
                sequence=1,
                description="",
                manifest_hash="2" * 64,
                validation_summary="测试夹具已校验",
                created_by=BOB_ID,
                created_at=now,
            ),
        ]
    )
    await session.flush()
    session.add_all(
        [
            t.SharedResourceVersionFileRow(
                version_id="shrv_visible_active_group",
                path="visible.txt",
                size=7,
                content_hash="a" * 64,
            ),
            t.SharedResourceVersionFileRow(
                version_id="shrv_hidden_bob",
                path="secret.txt",
                size=6,
                content_hash="b" * 64,
            ),
        ]
    )
    await session.flush()


@pytest.mark.asyncio
async def test_issue_39_repositories_discover_only_user_or_active_group_owned_assets(
    session: AsyncSession,
) -> None:
    await _seed_owners(session)
    repos = SqlRepositories(session)

    environments = await repos.environments.list_discoverable_for_user(ALICE_ID)
    resources = await repos.shared_resources.list_discoverable_for_user(ALICE_ID)

    assert {environment.id for environment in environments} == {
        "env_owned_by_alice",
        "env_owned_by_active_group",
    }
    assert {resource.id for resource in resources} == {
        "shr_owned_by_alice",
        "shr_owned_by_active_group",
    }
    assert {environment.owner for environment in environments} == {
        OwnerReference(OwnerKind.USER, ALICE_ID),
        OwnerReference(OwnerKind.USER_GROUP, ACTIVE_GROUP_ID),
    }
    assert {resource.owner for resource in resources} == {
        OwnerReference(OwnerKind.USER, ALICE_ID),
        OwnerReference(OwnerKind.USER_GROUP, ACTIVE_GROUP_ID),
    }

    assert await repos.environments.get_discoverable_for_user(ALICE_ID, "env_owned_by_bob") is None
    assert (
        await repos.shared_resources.get_discoverable_for_user(ALICE_ID, "shr_owned_by_bob") is None
    )
    assert (
        await repos.environments.get_discoverable_for_user(ALICE_ID, "env_owned_by_invited_group")
        is None
    )
    assert (
        await repos.environments.get_discoverable_for_user(ALICE_ID, "env_owned_by_removed_group")
        is None
    )
    assert (
        await repos.shared_resources.get_discoverable_for_user(ALICE_ID, "shr_owned_by_left_group")
        is None
    )
    assert (
        await repos.shared_resources.get_discoverable_for_user(ALICE_ID, "shr_owned_by_other_group")
        is None
    )

    assert (
        await repos.environments.get_version_discoverable_for_user(ALICE_ID, "ev_hidden_bob")
        is None
    )
    assert (
        await repos.shared_resources.get_version_discoverable_for_user(ALICE_ID, "shrv_hidden_bob")
        is None
    )
    visible_version = await repos.shared_resources.get_version_discoverable_for_user(
        ALICE_ID, "shrv_visible_active_group"
    )
    assert visible_version is not None
    assert [file.path for file in visible_version.files] == ["visible.txt"]
