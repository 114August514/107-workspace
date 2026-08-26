"""平台目录用例：运行环境与算力方案。

这些数据由平台管理员维护（设计稿 §2.13 E）。用例层存在的意义不只是转发——
api 层不应该知道「环境和它的版本要分两次查」这种细节，
以后目录换成缓存或外部服务，也只改这里。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.capabilities import Capability
from ..domain.compute import ComputePlan
from ..domain.errors import ObjectNotFound
from ..domain.models import Environment, EnvironmentVersion
from ..domain.ownership import OwnerKind, OwnerReference
from ..domain.ports.repositories import Repositories
from .access import AccessGuard
from .ownership import OwnerSummary, owner_summaries


@dataclass(frozen=True, slots=True)
class EnvironmentView:
    """一个运行环境及其全部已发布版本。"""

    environment: Environment
    versions: list[EnvironmentVersion]
    owner: OwnerSummary


class CatalogService:
    def __init__(self, repos: Repositories, guard: AccessGuard) -> None:
        self._repos = repos
        self._guard = guard

    async def list_environments(self, user_id: str) -> list[EnvironmentView]:
        environments = await self._repos.environments.list_usable_for_user(user_id)
        return await self._views(user_id, environments)

    async def list_for_user_group(self, user_id: str, user_group_id: str) -> list[EnvironmentView]:
        await self._guard.user_group(user_id, user_group_id)
        owner = OwnerReference(OwnerKind.USER_GROUP, user_group_id)
        environments = await self._repos.environments.list_usable_for_owner(user_id, owner)
        return await self._views(user_id, environments, owner=owner)

    async def list_for_project(self, user_id: str, project_id: str) -> list[EnvironmentView]:
        access = await self._guard.project(
            user_id,
            project_id,
            needs=Capability.RUN_CONFIGURATION_MANAGE,
            owner_scope=True,
        )
        environments = await self._repos.environments.list_usable_for_owner(
            user_id, access.project.owner
        )
        return await self._views(user_id, environments, owner=access.project.owner)

    async def get_environment(self, user_id: str, environment_id: str) -> EnvironmentView:
        environment = await self._repos.environments.get_usable_for_user(user_id, environment_id)
        if environment is None:
            raise ObjectNotFound("Environment", environment_id)
        return (await self._views(user_id, [environment]))[0]

    async def get_environment_version(self, user_id: str, version_id: str) -> EnvironmentVersion:
        version = await self._repos.environments.get_version_usable_for_user(user_id, version_id)
        if version is None:
            raise ObjectNotFound("Environment Version", version_id)
        return version

    async def _views(
        self,
        user_id: str,
        environments: list[Environment],
        *,
        owner: OwnerReference | None = None,
    ) -> list[EnvironmentView]:
        owners = await owner_summaries(
            self._repos, (environment.owner for environment in environments)
        )
        views: list[EnvironmentView] = []
        for environment in environments:
            if owner is None:
                versions = await self._repos.environments.list_versions_usable_for_user(
                    user_id, environment.id
                )
            else:
                versions = await self._repos.environments.list_versions_usable_for_owner(
                    user_id, owner, environment.id
                )
            views.append(
                EnvironmentView(
                    environment=environment,
                    versions=versions,
                    owner=owners[(environment.owner.kind, environment.owner.id)],
                )
            )
        return views

    async def list_compute_plans(self) -> list[ComputePlan]:
        return await self._repos.compute_plans.list_all()
