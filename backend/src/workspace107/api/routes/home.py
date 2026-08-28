"""Personal home projection."""

from __future__ import annotations

from fastapi import APIRouter

from ...application.ownership import OwnerSummary
from ...domain.ownership import OwnerKind
from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, ServicesDep

router = APIRouter(tags=["home"])


@router.get("/me", response_model=s.HomeOut, summary="获取个人首页")
async def home(user: CurrentUser, services: ServicesDep) -> s.HomeOut:
    """Return current identity, User Groups, direct execution context, and recent objects."""
    user_groups = await services.user_groups.list_for_user(user.id)
    projects = await services.projects.list_recent_for_user(user.id, limit=10)
    owner_summaries = await services.projects.owner_summaries(projects)
    entitlements = await services.entitlements.list_for_user(user.id)
    return s.HomeOut(
        user=p.user_out(user),
        user_groups=[p.user_group_out(group) for group in user_groups],
        personal_execution_context=s.PersonalExecutionContextOut(
            owner=p.owner_summary_out(
                OwnerSummary(kind=OwnerKind.USER, id=user.id, display_name=user.display_name)
            ),
            entitlements=[p.entitlement_out(view) for view in entitlements],
        ),
        recent_projects=[
            p.project_out(
                project,
                owner=owner_summaries[(project.owner.kind, project.owner.id)],
            )
            for project in projects
        ],
        recent_runs=[
            p.run_out(run) for run in await services.runs.list_recent_for_user(user.id, limit=10)
        ],
    )


@router.get(
    "/me/entitlements",
    response_model=list[s.EntitlementOut],
    summary="查看我的资源权益",
)
async def list_my_entitlements(user: CurrentUser, services: ServicesDep) -> list[s.EntitlementOut]:
    """Resource Entitlement 属于 User 本人，按发起 User 校验 Run 资格。"""
    return [p.entitlement_out(view) for view in await services.entitlements.list_for_user(user.id)]


@router.get("/invitations", response_model=list[s.InvitationOut], summary="我收到的邀请")
async def list_invitations(user: CurrentUser, services: ServicesDep) -> list[s.InvitationOut]:
    """Pending User Group invitations; an invited user cannot read group content yet."""
    return [p.invitation_out(view) for view in await services.user_groups.list_invitations(user.id)]
