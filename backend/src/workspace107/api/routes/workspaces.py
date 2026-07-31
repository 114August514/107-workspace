"""Workspace 路由。"""

from __future__ import annotations

from fastapi import APIRouter, status

from ...domain.enums import WorkspaceRole
from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, PageDep, ServicesDep

router = APIRouter(prefix="/workspaces", tags=["workspace"])


@router.get("", response_model=list[s.WorkspaceOut])
async def list_workspaces(user: CurrentUser, services: ServicesDep) -> list[s.WorkspaceOut]:
    views = await services.workspaces.list_for_user(user.id)
    return [p.workspace_out(view) for view in views]


@router.post("", response_model=s.WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: s.WorkspaceCreateIn, user: CurrentUser, services: ServicesDep
) -> s.WorkspaceOut:
    view = await services.workspaces.create_collaborative(
        user.id, payload.name, payload.description
    )
    return p.workspace_out(view)


@router.get("/{workspace_id}", response_model=s.WorkspaceOut)
async def get_workspace(
    workspace_id: str, user: CurrentUser, services: ServicesDep
) -> s.WorkspaceOut:
    return p.workspace_out(await services.workspaces.get(user.id, workspace_id))


@router.patch("/{workspace_id}", response_model=s.WorkspaceOut)
async def update_workspace(
    workspace_id: str,
    payload: s.WorkspaceUpdateIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.WorkspaceOut:
    await services.workspaces.update(
        user.id,
        workspace_id,
        name=payload.name,
        description=payload.description,
        default_environment_version_id=payload.default_environment_version_id,
    )
    return p.workspace_out(await services.workspaces.get(user.id, workspace_id))


# -- 成员 -------------------------------------------------------------------


@router.get("/{workspace_id}/members", response_model=list[s.MemberOut])
async def list_members(
    workspace_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.MemberOut]:
    views = await services.workspaces.list_members(user.id, workspace_id)
    return [p.member_out(v) for v in views]


@router.post(
    "/{workspace_id}/members", response_model=s.MemberOut, status_code=status.HTTP_201_CREATED
)
async def invite_member(
    workspace_id: str,
    payload: s.MemberInviteIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.MemberOut:
    await services.workspaces.invite_member(
        user.id, workspace_id, payload.username, WorkspaceRole(payload.role)
    )
    views = await services.workspaces.list_members(user.id, workspace_id)
    invited = next(v for v in views if v.user.username == payload.username)
    return p.member_out(invited)


@router.patch("/{workspace_id}/members/{target_user_id}", response_model=s.MemberOut)
async def change_member_role(
    workspace_id: str,
    target_user_id: str,
    payload: s.MemberRoleUpdateIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.MemberOut:
    await services.workspaces.change_member_role(
        user.id, workspace_id, target_user_id, payload.role
    )
    views = await services.workspaces.list_members(user.id, workspace_id)
    changed = next(view for view in views if view.user.id == target_user_id)
    return p.member_out(changed)


@router.delete("/{workspace_id}/members/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    workspace_id: str, target_user_id: str, user: CurrentUser, services: ServicesDep
) -> None:
    await services.workspaces.remove_member(user.id, workspace_id, target_user_id)


@router.post("/{workspace_id}/invitation", status_code=status.HTTP_204_NO_CONTENT)
async def respond_to_invitation(
    workspace_id: str,
    payload: s.InvitationResponseIn,
    user: CurrentUser,
    services: ServicesDep,
) -> None:
    await services.workspaces.respond_to_invitation(user.id, workspace_id, accept=payload.accept)


@router.post("/{workspace_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_workspace(workspace_id: str, user: CurrentUser, services: ServicesDep) -> None:
    await services.workspaces.leave(user.id, workspace_id)


@router.post(
    "/{workspace_id}/transfer-ownership/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def transfer_ownership(
    workspace_id: str, target_user_id: str, user: CurrentUser, services: ServicesDep
) -> None:
    await services.workspaces.transfer_ownership(user.id, workspace_id, target_user_id)


# -- 资源权益 ---------------------------------------------------------------


@router.get("/{workspace_id}/entitlements", response_model=list[s.EntitlementOut])
async def list_entitlements(
    workspace_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.EntitlementOut]:
    views = await services.workspaces.list_entitlements(user.id, workspace_id)
    return [p.entitlement_out(v) for v in views]


# -- Variable 与 Secret -----------------------------------------------------


@router.get("/{workspace_id}/variables", response_model=list[s.VariableOut])
async def list_variables(
    workspace_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.VariableOut]:
    variables = await services.workspaces.list_variables(user.id, workspace_id)
    return [s.VariableOut(name=v.name, value=v.value) for v in variables]


@router.put("/{workspace_id}/variables", response_model=s.VariableOut)
async def set_variable(
    workspace_id: str, payload: s.VariableIn, user: CurrentUser, services: ServicesDep
) -> s.VariableOut:
    variable = await services.workspaces.set_variable(
        user.id, workspace_id, payload.name, payload.value
    )
    return s.VariableOut(name=variable.name, value=variable.value)


@router.delete("/{workspace_id}/variables/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_variable(
    workspace_id: str, name: str, user: CurrentUser, services: ServicesDep
) -> None:
    await services.workspaces.delete_variable(user.id, workspace_id, name)


@router.get("/{workspace_id}/secrets", response_model=list[str])
async def list_secret_names(
    workspace_id: str, user: CurrentUser, services: ServicesDep
) -> list[str]:
    """只返回名称。Secret 的值没有任何读取接口（GR-012）。"""
    return await services.workspaces.list_secret_names(user.id, workspace_id)


@router.put("/{workspace_id}/secrets", status_code=status.HTTP_204_NO_CONTENT)
async def set_secret(
    workspace_id: str, payload: s.SecretIn, user: CurrentUser, services: ServicesDep
) -> None:
    await services.workspaces.set_secret(user.id, workspace_id, payload.name, payload.value)


@router.delete("/{workspace_id}/secrets/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(
    workspace_id: str, name: str, user: CurrentUser, services: ServicesDep
) -> None:
    await services.workspaces.delete_secret(user.id, workspace_id, name)


# -- Project ----------------------------------------------------------------


@router.get("/{workspace_id}/projects", response_model=s.PageOut[s.ProjectOut])
async def list_projects(
    workspace_id: str, user: CurrentUser, services: ServicesDep, page: PageDep
) -> s.PageOut[s.ProjectOut]:
    result = await services.projects.list_for_workspace(user.id, workspace_id, page)
    return p.page_out(result, p.project_out)


@router.post(
    "/{workspace_id}/projects", response_model=s.ProjectOut, status_code=status.HTTP_201_CREATED
)
async def create_project(
    workspace_id: str,
    payload: s.ProjectCreateIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.ProjectOut:
    project = await services.projects.create(
        user.id, workspace_id, payload.name, payload.description
    )
    return p.project_out(project)


@router.get(
    "/{workspace_id}/activities",
    response_model=s.PageOut[s.ActivityOut],
    summary="Workspace 近期活动",
)
async def list_workspace_activities(
    workspace_id: str, user: CurrentUser, services: ServicesDep, page: PageDep
) -> s.PageOut[s.ActivityOut]:
    result = await services.activities.list_for_workspace(user.id, workspace_id, page)
    return p.page_out(result, p.activity_out)
