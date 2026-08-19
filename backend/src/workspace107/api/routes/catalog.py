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
    user: CurrentUser,
    services: ServicesDep,
) -> list[s.EnvironmentOut]:
    """返回当前 User 作为 Owner 或 owning UserGroup active member 可发现的环境。"""
    views = await services.catalog.list_environments(user.id)
    return [p.environment_out(view) for view in views]


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
    summary="列出当前用户可发现的共享资源（兼容别名）",
    deprecated=True,
)
async def list_actor_shared_resources(
    user: CurrentUser,
    services: ServicesDep,
) -> list[s.SharedResourceOut]:
    """Deprecated actor-scoped alias; canonical path is ``GET /shared-resources``."""
    views = await services.shared_resources.list_actor_discoverable(user.id)
    return [p.shared_resource_out(view) for view in views]
