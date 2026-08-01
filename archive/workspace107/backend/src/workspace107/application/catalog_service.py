"""平台目录用例：运行环境与算力方案。

这些数据由平台管理员维护（设计稿 §2.13 E）。用例层存在的意义不只是转发——
api 层不应该知道「环境和它的版本要分两次查」这种细节，
以后目录换成缓存或外部服务，也只改这里。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.compute import ComputePlan
from ..domain.errors import ObjectNotFound
from ..domain.models import Environment, EnvironmentVersion
from ..domain.ports.repositories import Repositories


@dataclass(frozen=True, slots=True)
class EnvironmentView:
    """一个运行环境及其全部已发布版本。"""

    environment: Environment
    versions: list[EnvironmentVersion]


class CatalogService:
    def __init__(self, repos: Repositories) -> None:
        self._repos = repos

    async def list_environments(self) -> list[EnvironmentView]:
        views: list[EnvironmentView] = []
        for environment in await self._repos.environments.list_environments():
            versions = await self._repos.environments.list_versions(environment.id)
            views.append(EnvironmentView(environment=environment, versions=versions))
        return views

    async def get_environment_version(self, version_id: str) -> EnvironmentVersion:
        version = await self._repos.environments.get_version(version_id)
        if version is None:
            raise ObjectNotFound("Environment Version", version_id)
        return version

    async def list_compute_plans(self) -> list[ComputePlan]:
        return await self._repos.compute_plans.list_all()
