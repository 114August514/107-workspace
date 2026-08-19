from __future__ import annotations

import pytest
from sqlalchemy import select

from workspace107.api.deps import build_services
from workspace107.domain.enums import LegacyWorkspaceKind, MembershipRole, MembershipStatus
from workspace107.infrastructure.db import tables as t
from workspace107.tools.seed import DEMO_PROJECT, DEMO_USER, seed_demo

DEMO_USER_GROUP_ID = "grp_demo"
DEMO_OWNER_MEMBERSHIP_ID = "mbr_demo_owner"

PLATFORM_ASSET_GROUP_ID = "grp_platform_assets"
DEMO_ENVIRONMENT_ID = "env_demo_python_2026"
DEMO_ENVIRONMENT_VERSION_ID = "ev_demo_python_312_2026"
NEW_ENVIRONMENT_IDS = {
    "env_platform_python_base_2026",
    "env_platform_pytorch_2026",
    DEMO_ENVIRONMENT_ID,
}
NEW_ENVIRONMENT_VERSION_IDS = {
    "ev_platform_python_312_2026",
    "ev_platform_pytorch_24_2026",
    DEMO_ENVIRONMENT_VERSION_ID,
}
LEGACY_ASSET_IDS = {
    "env_python_base",
    "env_pytorch",
    "ev_python_312",
    "ev_pytorch_24",
}


async def _active_owner_id(session, user_group_id: str) -> str | None:
    return (
        await session.execute(
            select(t.MembershipRow.user_id).where(
                t.MembershipRow.user_group_id == user_group_id,
                t.MembershipRow.role == MembershipRole.OWNER.value,
                t.MembershipRow.status == MembershipStatus.ACTIVE.value,
            )
        )
    ).scalar_one_or_none()


async def _user_id_by_username(session, username: str) -> str | None:
    return (
        await session.execute(select(t.UserRow.id).where(t.UserRow.username == username))
    ).scalar_one_or_none()


@pytest.mark.asyncio
async def test_issue_39_non_demo_seed_creates_compute_plans_without_platform_assets(
    session,
) -> None:
    plans = list((await session.execute(select(t.ComputePlanRow))).scalars())
    environments = list((await session.execute(select(t.EnvironmentRow))).scalars())
    resources = list((await session.execute(select(t.SharedResourceRow))).scalars())

    assert plans
    assert environments == []
    assert resources == []
    assert await session.get(t.UserGroupRow, PLATFORM_ASSET_GROUP_ID) is None


@pytest.mark.asyncio
async def test_issue_39_demo_seed_uses_explicit_bootstrap_owner_and_preserves_transfer(
    context, session, monkeypatch: pytest.MonkeyPatch
) -> None:
    services = build_services(context, session)
    monkeypatch.setenv("WORKSPACE107_DEMO_PLATFORM_OWNER_USERNAME", "must-lose-to-cli")

    await seed_demo(session, context, platform_owner_username="platform-bootstrap-owner")
    initial_owner_id = await _user_id_by_username(session, "platform-bootstrap-owner")
    assert initial_owner_id is not None
    platform_group = await session.get(t.UserGroupRow, PLATFORM_ASSET_GROUP_ID)
    assert platform_group is not None
    assert await _active_owner_id(session, PLATFORM_ASSET_GROUP_ID) == initial_owner_id
    assert await _user_id_by_username(session, "must-lose-to-cli") is None

    environments = list((await session.execute(select(t.EnvironmentRow))).scalars())
    versions = list((await session.execute(select(t.EnvironmentVersionRow))).scalars())
    assert {environment.id for environment in environments} == NEW_ENVIRONMENT_IDS
    assert {version.id for version in versions} == NEW_ENVIRONMENT_VERSION_IDS
    assert all(environment.owner_user_id is None for environment in environments)
    expected_owners = {
        "env_platform_python_base_2026": PLATFORM_ASSET_GROUP_ID,
        "env_platform_pytorch_2026": PLATFORM_ASSET_GROUP_ID,
        DEMO_ENVIRONMENT_ID: DEMO_USER_GROUP_ID,
    }
    assert {
        environment.id: environment.owner_user_group_id for environment in environments
    } == expected_owners
    assert LEGACY_ASSET_IDS.isdisjoint(
        {environment.id for environment in environments} | {version.id for version in versions}
    )

    successor = await services.identity.ensure_user("platform-operator-2", "Platform Operator 2")
    await services.user_groups.invite_member(
        initial_owner_id,
        PLATFORM_ASSET_GROUP_ID,
        successor.username,
        MembershipRole.ADMIN,
    )
    await services.user_groups.respond_to_invitation(
        successor.id, PLATFORM_ASSET_GROUP_ID, accept=True
    )
    await services.user_groups.transfer_ownership(
        initial_owner_id, PLATFORM_ASSET_GROUP_ID, successor.id
    )

    await seed_demo(session, context, platform_owner_username="must-not-be-created")

    assert await _active_owner_id(session, PLATFORM_ASSET_GROUP_ID) == successor.id
    assert await _user_id_by_username(session, "must-not-be-created") is None
    persisted_environments = list((await session.execute(select(t.EnvironmentRow))).scalars())
    assert {environment.id for environment in persisted_environments} == NEW_ENVIRONMENT_IDS
    assert {
        environment.id: environment.owner_user_group_id for environment in persisted_environments
    } == expected_owners


@pytest.mark.asyncio
async def test_issue_39_demo_seed_uses_environment_owner_when_cli_value_absent(
    context, session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WORKSPACE107_DEMO_PLATFORM_OWNER_USERNAME", "owner-from-env")

    await seed_demo(session, context)

    owner_id = await _user_id_by_username(session, "owner-from-env")
    assert owner_id is not None
    assert await _active_owner_id(session, PLATFORM_ASSET_GROUP_ID) == owner_id


@pytest.mark.asyncio
async def test_issue_39_platform_seed_completes_partial_records_and_rejects_drift(
    context, session
) -> None:
    await seed_demo(session, context)
    version = await session.get(t.EnvironmentVersionRow, "ev_platform_pytorch_24_2026")
    environment = await session.get(t.EnvironmentRow, "env_platform_pytorch_2026")
    assert version is not None and environment is not None
    await session.delete(version)
    await session.flush()
    await session.delete(environment)
    await session.commit()

    await seed_demo(session, context)
    restored_version = await session.get(t.EnvironmentVersionRow, "ev_platform_pytorch_24_2026")
    restored_environment = await session.get(t.EnvironmentRow, "env_platform_pytorch_2026")
    assert restored_version is not None and restored_environment is not None

    restored_environment.owner_user_group_id = DEMO_USER_GROUP_ID
    await session.commit()
    with pytest.raises(RuntimeError, match="conflicting fixed Environment"):
        await seed_demo(session, context)
    await session.rollback()

    restored_environment = await session.get(t.EnvironmentRow, "env_platform_pytorch_2026")
    assert restored_environment is not None
    restored_environment.owner_user_group_id = PLATFORM_ASSET_GROUP_ID
    restored_version = await session.get(t.EnvironmentVersionRow, "ev_platform_pytorch_24_2026")
    assert restored_version is not None
    restored_version.image = "conflicting:image"
    await session.commit()
    with pytest.raises(RuntimeError, match="conflicting fixed EnvironmentVersion"):
        await seed_demo(session, context)


@pytest.mark.asyncio
async def test_issue_35_demo_seed_uses_only_its_deterministic_group(context, session) -> None:
    services = build_services(context, session)
    user = await services.identity.ensure_user(DEMO_USER, "演示同学")
    unrelated = (
        await services.user_groups.create(user.id, "Ordinary Group", "Must remain ordinary")
    ).user_group

    first_project_id = await seed_demo(session, context)
    second_project_id = await seed_demo(session, context)
    await session.commit()
    assert await _active_owner_id(session, PLATFORM_ASSET_GROUP_ID) == user.id

    demo_group = await session.get(t.UserGroupRow, DEMO_USER_GROUP_ID)
    assert demo_group is not None
    assert demo_group.created_by_id == user.id

    demo_anchor = await session.get(t.LegacyWorkspaceRow, DEMO_USER_GROUP_ID)
    assert demo_anchor is not None
    assert demo_anchor.kind == LegacyWorkspaceKind.COLLABORATIVE.value
    assert demo_anchor.owner_id == user.id

    demo_owner = await session.get(t.MembershipRow, DEMO_OWNER_MEMBERSHIP_ID)
    assert demo_owner is not None
    assert (
        demo_owner.user_group_id,
        demo_owner.user_id,
        demo_owner.role,
        demo_owner.status,
    ) == (
        DEMO_USER_GROUP_ID,
        user.id,
        MembershipRole.OWNER.value,
        MembershipStatus.ACTIVE.value,
    )

    entitlements = list((await session.execute(select(t.ResourceEntitlementRow))).scalars())
    assert {(item.workspace_id, item.compute_plan_id) for item in entitlements} == {
        (DEMO_USER_GROUP_ID, "plan_cpu_quick")
    }

    unrelated_after = await session.get(t.UserGroupRow, unrelated.id)
    assert unrelated_after is not None
    assert (
        unrelated_after.name,
        unrelated_after.description,
        unrelated_after.created_by_id,
    ) == ("Ordinary Group", "Must remain ordinary", user.id)

    demo_projects = list(
        (
            await session.execute(
                select(t.ProjectRow).where(t.ProjectRow.workspace_id == DEMO_USER_GROUP_ID)
            )
        ).scalars()
    )
    unrelated_projects = list(
        (
            await session.execute(
                select(t.ProjectRow).where(t.ProjectRow.workspace_id == unrelated.id)
            )
        ).scalars()
    )
    assert first_project_id == second_project_id
    assert {(project.id, project.name) for project in demo_projects} == {
        (first_project_id, DEMO_PROJECT)
    }
    assert unrelated_projects == []
