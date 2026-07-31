"""平台目录：运行环境与算力方案。"""

from __future__ import annotations

from fastapi import APIRouter

from .. import presenters as p
from .. import schemas as s
from ..deps import CurrentUser, ServicesDep

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/environments", response_model=list[s.EnvironmentOut])
async def list_environments(
    user: CurrentUser,  # 目录接口要求登录，但不区分用户
    services: ServicesDep,
) -> list[s.EnvironmentOut]:
    views = await services.catalog.list_environments()
    return [p.environment_out(view.environment, view.versions) for view in views]


@router.get("/compute-plans", response_model=list[s.ComputePlanOut])
async def list_compute_plans(
    user: CurrentUser,
    services: ServicesDep,
) -> list[s.ComputePlanOut]:
    plans = await services.catalog.list_compute_plans()
    return [p.compute_plan_out(plan) for plan in plans]
