"""个人首页。

对应设计稿 2.1：查看个人信息、自己拥有和参与的 Workspace、
最近使用的 Project 和最近提交的 Run。
"""

from __future__ import annotations

from fastapi import APIRouter

from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, ServicesDep

router = APIRouter(tags=["home"])


@router.get("/me", response_model=s.HomeOut)
async def home(user: CurrentUser, services: ServicesDep) -> s.HomeOut:
    workspaces = await services.workspaces.list_for_user(user.id)
    return s.HomeOut(
        user=p.user_out(user),
        workspaces=[p.workspace_out(w) for w in workspaces],
        recent_projects=[
            p.project_out(project)
            for project in await services.projects.list_recent_for_user(user.id, limit=10)
        ],
        recent_runs=[
            p.run_out(run) for run in await services.runs.list_recent_for_user(user.id, limit=10)
        ],
    )


@router.get("/invitations", response_model=list[s.InvitationOut], summary="我收到的邀请")
async def list_invitations(user: CurrentUser, services: ServicesDep) -> list[s.InvitationOut]:
    """待处理的 Workspace 邀请。

    单独一个接口，不并进 `/workspaces`——被邀请的人还不该看到空间里的内容，
    只该看到「有人邀请你，接受还是拒绝」。接受用
    `POST /workspaces/{id}/invitation`。
    """
    return [p.invitation_out(view) for view in await services.workspaces.list_invitations(user.id)]
