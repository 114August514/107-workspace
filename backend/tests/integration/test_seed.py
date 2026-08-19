from __future__ import annotations

import pytest
from sqlalchemy import select

from workspace107.api.deps import build_services
from workspace107.domain.enums import LegacyWorkspaceKind, MembershipRole, MembershipStatus
from workspace107.infrastructure.db import tables as t
from workspace107.tools.seed import DEMO_PROJECT, DEMO_USER, seed_demo

DEMO_USER_GROUP_ID = "grp_demo"
DEMO_OWNER_MEMBERSHIP_ID = "mbr_demo_owner"


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
