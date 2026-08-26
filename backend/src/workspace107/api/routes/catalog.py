"""Platform catalog for environments and compute plans."""

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
    """返回当前 User 可在个人或有效 User Group Owner 上下文中使用的环境。"""
    views = await services.catalog.list_environments(user.id)
    return [p.environment_out(view) for view in views]


@router.get(
    "/environments/{environment_id}",
    response_model=s.EnvironmentOut,
    summary="获取运行环境",
)
async def get_environment(
    environment_id: str,
    user: CurrentUser,
    services: ServicesDep,
) -> s.EnvironmentOut:
    return p.environment_out(await services.catalog.get_environment(user.id, environment_id))


@router.get(
    "/environment-versions/{version_id}",
    response_model=s.EnvironmentVersionOut,
    summary="获取运行环境版本",
)
async def get_environment_version(
    version_id: str,
    user: CurrentUser,
    services: ServicesDep,
) -> s.EnvironmentVersionOut:
    return p.environment_version_out(
        await services.catalog.get_environment_version(user.id, version_id)
    )


@router.get(
    "/compute-plans",
    response_model=list[s.ComputePlanOut],
    summary="列出算力方案",
)
async def list_compute_plans(
    user: CurrentUser,
    services: ServicesDep,
) -> list[s.ComputePlanOut]:
    """登录后只读返回平台全部算力方案；列表不表示当前 User 已获得对应权益。"""
    plans = await services.catalog.list_compute_plans()
    return [p.compute_plan_out(plan) for plan in plans]
