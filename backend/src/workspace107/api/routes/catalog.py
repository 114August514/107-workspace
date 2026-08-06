"""平台目录：运行环境与算力方案。"""

from __future__ import annotations

from fastapi import APIRouter

from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, ServicesDep

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get(
    "/environments",
    response_model=list[s.EnvironmentOut],
    summary="列出运行环境",
)
async def list_environments(
    user: CurrentUser,  # 目录接口要求登录，但不区分用户
    services: ServicesDep,
) -> list[s.EnvironmentOut]:
    """登录后只读返回平台统一维护的运行环境及其全部已发布版本，不按用户区分。"""
    views = await services.catalog.list_environments()
    return [p.environment_out(view.environment, view.versions) for view in views]


@router.get(
    "/compute-plans",
    response_model=list[s.ComputePlanOut],
    summary="列出算力方案",
)
async def list_compute_plans(
    user: CurrentUser,
    services: ServicesDep,
) -> list[s.ComputePlanOut]:
    """登录后只读返回平台全部算力方案；列表不表示当前 Workspace 已获得对应权益。"""
    plans = await services.catalog.list_compute_plans()
    return [p.compute_plan_out(plan) for plan in plans]


@router.get(
    "/shared-resources",
    response_model=list[s.SharedResourceOut],
    summary="列出 Platform 持有的共享资源",
)
async def list_platform_shared_resources(
    user: CurrentUser,
    services: ServicesDep,
) -> list[s.SharedResourceOut]:
    """登录后只读返回 Platform 持有的 Shared Resource，不按用户区分。

    Workspace 持有的资源请走 ``GET /workspaces/{id}/shared-resources``；
    跨 Workspace Asset Grant 在 M4 单独 Issue。
    """
    resources = await services.shared_resources.list_platform(user.id)
    return [p.shared_resource_out(r) for r in resources]
