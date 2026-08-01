"""Workspace 路由。"""

from __future__ import annotations

from fastapi import APIRouter, status

from ...domain.enums import WorkspaceRole
from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, PageDep, ServicesDep

router = APIRouter(prefix="/workspaces", tags=["workspace"])


@router.get("", response_model=list[s.WorkspaceOut], summary="列出我的 Workspace")
async def list_workspaces(user: CurrentUser, services: ServicesDep) -> list[s.WorkspaceOut]:
    """返回当前用户拥有或已加入的 Workspace，并附带其角色与可用能力。"""
    views = await services.workspaces.list_for_user(user.id)
    return [p.workspace_out(view) for view in views]


@router.post(
    "",
    response_model=s.WorkspaceOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建协作 Workspace",
)
async def create_workspace(
    payload: s.WorkspaceCreateIn, user: CurrentUser, services: ServicesDep
) -> s.WorkspaceOut:
    """创建协作 Workspace，当前用户成为 Owner，同时授予默认资源权益并记录活动。"""
    view = await services.workspaces.create_collaborative(
        user.id, payload.name, payload.description
    )
    return p.workspace_out(view)


@router.get("/{workspace_id}", response_model=s.WorkspaceOut, summary="获取 Workspace 详情")
async def get_workspace(
    workspace_id: str, user: CurrentUser, services: ServicesDep
) -> s.WorkspaceOut:
    """仅对可访问该 Workspace 的用户返回详情、当前角色和可用能力。"""
    return p.workspace_out(await services.workspaces.get(user.id, workspace_id))


@router.patch("/{workspace_id}", response_model=s.WorkspaceOut, summary="更新 Workspace 设置")
async def update_workspace(
    workspace_id: str,
    payload: s.WorkspaceUpdateIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.WorkspaceOut:
    """需要修改空间设置权限；更新请求中提供的字段，并记录 Workspace 更新活动。"""
    await services.workspaces.update(
        user.id,
        workspace_id,
        name=payload.name,
        description=payload.description,
        default_environment_version_id=payload.default_environment_version_id,
    )
    return p.workspace_out(await services.workspaces.get(user.id, workspace_id))


# -- 成员 -------------------------------------------------------------------


@router.get(
    "/{workspace_id}/members", response_model=list[s.MemberOut], summary="列出 Workspace 成员"
)
async def list_members(
    workspace_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.MemberOut]:
    """需要查看成员权限；Personal Workspace 返回其所有者对应的虚拟成员。"""
    views = await services.workspaces.list_members(user.id, workspace_id)
    return [p.member_out(v) for v in views]


@router.post(
    "/{workspace_id}/members",
    response_model=s.MemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="邀请 Workspace 成员",
)
async def invite_member(
    workspace_id: str,
    payload: s.MemberInviteIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.MemberOut:
    """需要管理成员权限；向协作 Workspace 发出非 Owner 角色邀请，并记录活动、通知用户。"""
    await services.workspaces.invite_member(
        user.id, workspace_id, payload.username, WorkspaceRole(payload.role)
    )
    views = await services.workspaces.list_members(user.id, workspace_id)
    invited = next(v for v in views if v.user.username == payload.username)
    return p.member_out(invited)


@router.patch(
    "/{workspace_id}/members/{target_user_id}",
    response_model=s.MemberOut,
    summary="修改 Workspace 成员角色",
)
async def change_member_role(
    workspace_id: str,
    target_user_id: str,
    payload: s.MemberRoleUpdateIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.MemberOut:
    """需要管理成员权限；仅修改有效成员，Owner 需走转让接口，成功后记录活动并通知成员。"""
    await services.workspaces.change_member_role(
        user.id, workspace_id, target_user_id, payload.role
    )
    views = await services.workspaces.list_members(user.id, workspace_id)
    changed = next(view for view in views if view.user.id == target_user_id)
    return p.member_out(changed)


@router.delete(
    "/{workspace_id}/members/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="移除 Workspace 成员",
)
async def remove_member(
    workspace_id: str, target_user_id: str, user: CurrentUser, services: ServicesDep
) -> None:
    """需要管理成员权限；不能移除 Owner，首次移除会记录活动并通知成员。"""
    await services.workspaces.remove_member(user.id, workspace_id, target_user_id)


@router.post(
    "/{workspace_id}/invitation",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="处理 Workspace 邀请",
)
async def respond_to_invitation(
    workspace_id: str,
    payload: s.InvitationResponseIn,
    user: CurrentUser,
    services: ServicesDep,
) -> None:
    """处理当前用户自己的待定邀请；接受会激活成员并记录活动，拒绝不写入活动流。"""
    await services.workspaces.respond_to_invitation(user.id, workspace_id, accept=payload.accept)


@router.post(
    "/{workspace_id}/leave", status_code=status.HTTP_204_NO_CONTENT, summary="退出 Workspace"
)
async def leave_workspace(workspace_id: str, user: CurrentUser, services: ServicesDep) -> None:
    """退出当前用户已加入的协作 Workspace；Owner 必须先转让所有权。"""
    await services.workspaces.leave(user.id, workspace_id)


@router.post(
    "/{workspace_id}/transfer-ownership/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="转让 Workspace 所有权",
)
async def transfer_ownership(
    workspace_id: str, target_user_id: str, user: CurrentUser, services: ServicesDep
) -> None:
    """仅 Owner 可将协作 Workspace 转给有效成员；原 Owner 保留为 Admin。"""
    await services.workspaces.transfer_ownership(user.id, workspace_id, target_user_id)


# -- 资源权益 ---------------------------------------------------------------


@router.get(
    "/{workspace_id}/entitlements",
    response_model=list[s.EntitlementOut],
    summary="列出 Workspace 资源权益",
)
async def list_entitlements(
    workspace_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.EntitlementOut]:
    """需要查看资源权益权限；返回 Workspace 可用的算力方案及并发额度。"""
    views = await services.workspaces.list_entitlements(user.id, workspace_id)
    return [p.entitlement_out(v) for v in views]


# -- Variable 与 Secret -----------------------------------------------------


@router.get(
    "/{workspace_id}/variables",
    response_model=list[s.VariableOut],
    summary="列出 Workspace 变量",
)
async def list_variables(
    workspace_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.VariableOut]:
    """需要查看配置权限；返回 Workspace Variable 的名称和值。"""
    variables = await services.workspaces.list_variables(user.id, workspace_id)
    return [s.VariableOut(name=v.name, value=v.value) for v in variables]


@router.put(
    "/{workspace_id}/variables", response_model=s.VariableOut, summary="设置 Workspace 变量"
)
async def set_variable(
    workspace_id: str, payload: s.VariableIn, user: CurrentUser, services: ServicesDep
) -> s.VariableOut:
    """需要管理配置权限；按名称新增 Variable，或覆盖其现有值。"""
    variable = await services.workspaces.set_variable(
        user.id, workspace_id, payload.name, payload.value
    )
    return s.VariableOut(name=variable.name, value=variable.value)


@router.delete(
    "/{workspace_id}/variables/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除 Workspace 变量",
)
async def delete_variable(
    workspace_id: str, name: str, user: CurrentUser, services: ServicesDep
) -> None:
    """需要管理配置权限；按名称删除 Workspace Variable。"""
    await services.workspaces.delete_variable(user.id, workspace_id, name)


@router.get(
    "/{workspace_id}/secrets", response_model=list[str], summary="列出 Workspace Secret 名称"
)
async def list_secret_names(
    workspace_id: str, user: CurrentUser, services: ServicesDep
) -> list[str]:
    """需要查看配置权限。只返回名称。Secret 的值没有任何读取接口（设计稿 §3.1.4）。"""
    return await services.workspaces.list_secret_names(user.id, workspace_id)


@router.put(
    "/{workspace_id}/secrets",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="设置 Workspace Secret",
)
async def set_secret(
    workspace_id: str, payload: s.SecretIn, user: CurrentUser, services: ServicesDep
) -> None:
    """需要管理配置权限；写入非空 Secret 值，但响应及后续读取均不返回明文。"""
    await services.workspaces.set_secret(user.id, workspace_id, payload.name, payload.value)


@router.delete(
    "/{workspace_id}/secrets/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除 Workspace Secret",
)
async def delete_secret(
    workspace_id: str, name: str, user: CurrentUser, services: ServicesDep
) -> None:
    """需要管理配置权限；按名称删除 Workspace Secret。"""
    await services.workspaces.delete_secret(user.id, workspace_id, name)


# -- Project ----------------------------------------------------------------


@router.get(
    "/{workspace_id}/projects",
    response_model=s.PageOut[s.ProjectOut],
    summary="列出 Workspace 的 Project",
)
async def list_projects(
    workspace_id: str, user: CurrentUser, services: ServicesDep, page: PageDep
) -> s.PageOut[s.ProjectOut]:
    """需要查看 Project 权限；分页返回指定 Workspace 中的 Project。"""
    result = await services.projects.list_for_workspace(user.id, workspace_id, page)
    return p.page_out(result, p.project_out)


@router.post(
    "/{workspace_id}/projects",
    response_model=s.ProjectOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建 Workspace Project",
)
async def create_project(
    workspace_id: str,
    payload: s.ProjectCreateIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.ProjectOut:
    """需要创建 Project 权限；名称在 Workspace 内唯一，创建成功后记录活动。"""
    project = await services.projects.create(
        user.id, workspace_id, payload.name, payload.description
    )
    return p.project_out(project)


@router.get(
    "/{workspace_id}/activities",
    response_model=s.PageOut[s.ActivityOut],
    summary="列出 Workspace 活动",
)
async def list_workspace_activities(
    workspace_id: str, user: CurrentUser, services: ServicesDep, page: PageDep
) -> s.PageOut[s.ActivityOut]:
    """可查看 Workspace 的成员均可分页读取其活动流，无需额外的活动查看权限。"""
    result = await services.activities.list_for_workspace(user.id, workspace_id, page)
    return p.page_out(result, p.activity_out)
