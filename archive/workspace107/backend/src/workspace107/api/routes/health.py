"""健康检查与就绪探针。"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from ... import __version__
from ...observability import current_request_id
from .. import schemas as s
from ..deps import ContextDep, ServicesDep

router = APIRouter(tags=["health"])


@router.get("/health", response_model=s.HealthOut)
async def health(context: ContextDep) -> s.HealthOut:
    """进程是否活着。不检查任何外部依赖，所以它不会因为数据库抖动而失败。"""
    return s.HealthOut(
        status="ok",
        version=__version__,
        scheduler=context.scheduler.name,
        env=context.settings.env,
        request_id=current_request_id(),
    )


@router.get(
    "/ready",
    response_model=s.ReadinessOut,
    responses={503: {"model": s.ReadinessOut, "description": "依赖不可用，不应接收流量"}},
)
async def ready(services: ServicesDep, response: Response) -> s.ReadinessOut:
    """依赖是否都通。数据库连不上就返回 503，让上游把流量转走。"""
    report = await services.health.check_readiness()
    if not report.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return s.ReadinessOut(
        ready=report.ready,
        database=report.database,
        detail=report.detail,
        request_id=current_request_id(),
    )
