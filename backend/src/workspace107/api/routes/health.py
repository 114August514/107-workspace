"""健康检查与就绪探针。"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from ... import __version__
from ...observability import current_request_id
from .. import schemas as s
from ..deps import ContextDep, ServicesDep

router = APIRouter(tags=["health"])


@router.get("/health", response_model=s.HealthOut, summary="检查服务存活状态")
async def health(context: ContextDep) -> s.HealthOut:
    """无需登录，只报告 API 进程是否存活。

    此探针不检查数据库等外部依赖，因此依赖短暂故障不会触发容器重启。
    """
    return s.HealthOut(
        status="ok",
        version=__version__,
        scheduler="independent-worker",
        env=context.settings.env,
        request_id=current_request_id(),
    )


@router.get(
    "/ready",
    response_model=s.ReadinessOut,
    summary="检查服务就绪状态",
    responses={503: {"model": s.ReadinessOut, "description": "依赖不可用，不应接收流量"}},
)
async def ready(services: ServicesDep, response: Response) -> s.ReadinessOut:
    """无需登录，检查接收流量所需的数据库连接。

    依赖可用时返回 200；数据库不可用时返回 503，且不向调用方暴露底层异常细节。
    """
    report = await services.health.check_readiness()
    if not report.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return s.ReadinessOut(
        ready=report.ready,
        database=report.database,
        detail=report.detail,
        request_id=current_request_id(),
    )
