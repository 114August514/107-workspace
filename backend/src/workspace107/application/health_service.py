"""健康与就绪检查。

两个问题要分开回答：

    进程活着吗          -> /health，只要能返回就说明服务在跑
    依赖都通吗          -> /ready，数据库连不上就不该接流量

部署时用途不同：/health 决定要不要重启容器，/ready 决定要不要把流量转进来。
混成一个的话，数据库短暂抖动会导致容器被反复重启，反而更糟。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..domain.ports.repositories import Repositories

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    database: bool
    detail: str = ""

    @property
    def ready(self) -> bool:
        return self.database


class HealthService:
    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    async def check_readiness(self) -> ReadinessReport:
        try:
            await self._repos.ping()
        except Exception as exc:
            # 这里必须吞掉异常：探针的职责是回答「行不行」，
            # 而不是把数据库的报错细节透给调用方。原因留在日志里。
            logger.warning("就绪检查失败：数据库不可用", exc_info=exc)
            return ReadinessReport(database=False, detail="数据库不可用")
        return ReadinessReport(database=True)
