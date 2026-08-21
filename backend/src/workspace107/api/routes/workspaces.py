"""Deprecated downstream compatibility routes keyed by workspace_id.

No User Group governance operation belongs here. Delete each route with its owner slice
(#36 Project, #37 config, #38 entitlement, #42 activity/context).
"""

from __future__ import annotations

from fastapi import APIRouter, status

from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, PageDep, ServicesDep

router = APIRouter(prefix="/workspaces", tags=["deprecated-workspace-compatibility"])


@router.get(
    "/{workspace_id}",
    response_model=s.LegacyWorkspaceContextOut,
    summary="读取旧 workspace_id 上下文",
    deprecated=True,
)
async def get_legacy_workspace_context(
    workspace_id: str, user: CurrentUser, services: ServicesDep
) -> s.LegacyWorkspaceContextOut:
    return p.legacy_workspace_context_out(
        await services.legacy_workspaces.get(user.id, workspace_id)
    )


@router.patch(
    "/{workspace_id}",
    response_model=s.LegacyWorkspaceContextOut,
    summary="设置旧默认环境上下文",
    deprecated=True,
)
async def update_legacy_workspace_context(
    workspace_id: str,
    payload: s.LegacyWorkspaceUpdateIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.LegacyWorkspaceContextOut:
    await services.legacy_workspaces.set_default_environment(
        user.id, workspace_id, payload.default_environment_version_id
    )
    return p.legacy_workspace_context_out(
        await services.legacy_workspaces.get(user.id, workspace_id)
    )


@router.get(
    "/{workspace_id}/entitlements",
    response_model=list[s.EntitlementOut],
    summary="列出旧 Workspace 资源权益",
    deprecated=True,
)
async def list_entitlements(
    workspace_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.EntitlementOut]:
    return [
        p.entitlement_out(view)
        for view in await services.legacy_workspaces.list_entitlements(user.id, workspace_id)
    ]


@router.get(
    "/{workspace_id}/variables",
    response_model=list[s.VariableOut],
    summary="列出旧 Workspace Variable",
    deprecated=True,
)
async def list_variables(
    workspace_id: str, user: CurrentUser, services: ServicesDep
) -> list[s.VariableOut]:
    variables = await services.legacy_workspaces.list_variables(user.id, workspace_id)
    return [s.VariableOut(name=item.name, value=item.value) for item in variables]


@router.put(
    "/{workspace_id}/variables",
    response_model=s.VariableOut,
    summary="设置旧 Workspace Variable",
    deprecated=True,
)
async def set_variable(
    workspace_id: str, payload: s.VariableIn, user: CurrentUser, services: ServicesDep
) -> s.VariableOut:
    variable = await services.legacy_workspaces.set_variable(
        user.id, workspace_id, payload.name, payload.value
    )
    return s.VariableOut(name=variable.name, value=variable.value)


@router.delete(
    "/{workspace_id}/variables/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除旧 Workspace Variable",
    deprecated=True,
)
async def delete_variable(
    workspace_id: str, name: str, user: CurrentUser, services: ServicesDep
) -> None:
    await services.legacy_workspaces.delete_variable(user.id, workspace_id, name)


@router.get(
    "/{workspace_id}/secrets",
    response_model=list[str],
    summary="列出旧 Workspace Secret 名称",
    deprecated=True,
)
async def list_secret_names(
    workspace_id: str, user: CurrentUser, services: ServicesDep
) -> list[str]:
    return await services.legacy_workspaces.list_secret_names(user.id, workspace_id)


@router.put(
    "/{workspace_id}/secrets",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="设置旧 Workspace Secret",
    deprecated=True,
)
async def set_secret(
    workspace_id: str, payload: s.SecretIn, user: CurrentUser, services: ServicesDep
) -> None:
    await services.legacy_workspaces.set_secret(user.id, workspace_id, payload.name, payload.value)


@router.delete(
    "/{workspace_id}/secrets/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除旧 Workspace Secret",
    deprecated=True,
)
async def delete_secret(
    workspace_id: str, name: str, user: CurrentUser, services: ServicesDep
) -> None:
    await services.legacy_workspaces.delete_secret(user.id, workspace_id, name)


@router.get(
    "/{workspace_id}/projects",
    response_model=s.PageOut[s.ProjectOut],
    summary="列出旧 workspace_id 下的 Project",
    deprecated=True,
)
async def list_projects(
    workspace_id: str, user: CurrentUser, services: ServicesDep, page: PageDep
) -> s.PageOut[s.ProjectOut]:
    result = await services.projects.list_for_workspace(user.id, workspace_id, page)
    return p.page_out(result, p.project_out)


@router.post(
    "/{workspace_id}/projects",
    response_model=s.ProjectOut,
    status_code=status.HTTP_201_CREATED,
    summary="在旧 workspace_id 下创建 Project",
    deprecated=True,
)
async def create_project(
    workspace_id: str,
    payload: s.ProjectCreateIn,
    user: CurrentUser,
    services: ServicesDep,
) -> s.ProjectOut:
    return p.project_out(
        await services.projects.create(user.id, workspace_id, payload.name, payload.description),
        owner_scope=True,
    )


@router.get(
    "/{workspace_id}/activities",
    response_model=s.PageOut[s.ActivityOut],
    summary="列出旧 Workspace Activity",
    deprecated=True,
)
async def list_workspace_activities(
    workspace_id: str, user: CurrentUser, services: ServicesDep, page: PageDep
) -> s.PageOut[s.ActivityOut]:
    return p.page_out(
        await services.activities.list_for_workspace(user.id, workspace_id, page), p.activity_out
    )
