"""Current-user Environment catalog and platform Compute Plan reads."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.capabilities import Capability
from ..domain.compute import ComputePlan
from ..domain.errors import ObjectNotFound
from ..domain.grant import GrantTargetKind
from ..domain.models import Environment, EnvironmentVersion
from ..domain.ownership import OwnerKind, OwnerReference
from ..domain.ports.repositories import Repositories
from .access import AccessGuard
from .asset_use import environment_for_owner_use
from .ownership import OwnerSummary, owner_summaries


@dataclass(frozen=True, slots=True)
class EnvironmentView:
    """一个运行环境及其全部已发布版本。"""

    environment: Environment
    versions: list[EnvironmentVersion]
    owner: OwnerSummary
    capabilities: frozenset[Capability] = frozenset()


class CatalogService:
    def __init__(self, repos: Repositories, guard: AccessGuard) -> None:
        self._repos = repos
        self._guard = guard

    async def list_environments(self, user_id: str) -> list[EnvironmentView]:
        contexts = await self._owner_contexts(user_id)
        environments = await self._usable_environments(user_id, contexts)
        return await self._views(environments, user_id)

    async def list_for_project(self, user_id: str, project_id: str) -> list[EnvironmentView]:
        access = await self._guard.project(
            user_id,
            project_id,
            needs=Capability.RUN_CONFIGURATION_MANAGE,
            owner_scope=True,
        )
        environments = await self._usable_environments(user_id, [access.project.owner])
        return await self._views(environments, user_id)

    async def get_environment(self, user_id: str, environment_id: str) -> EnvironmentView:
        environment = await self._repos.environments.get_by_id(environment_id)
        if environment is None or not await self._usable_in_any_context(
            user_id, environment, await self._owner_contexts(user_id)
        ):
            raise ObjectNotFound("Environment", environment_id)
        return (await self._views([environment], user_id))[0]

    async def get_environment_version(self, user_id: str, version_id: str) -> EnvironmentVersion:
        version = await self._repos.environments.get_version_by_id(version_id)
        if version is None:
            raise ObjectNotFound("Environment Version", version_id)
        environment = await self._repos.environments.get_by_id(version.environment_id)
        if environment is None or not await self._usable_in_any_context(
            user_id, environment, await self._owner_contexts(user_id)
        ):
            raise ObjectNotFound("Environment Version", version_id)
        return version

    async def _owner_contexts(self, user_id: str) -> list[OwnerReference]:
        groups = await self._repos.user_groups.list_for_user(user_id)
        return [
            OwnerReference(OwnerKind.USER, user_id),
            *(group.owner_reference for group in groups),
        ]

    async def _usable_environments(
        self,
        user_id: str,
        contexts: list[OwnerReference],
    ) -> list[Environment]:
        candidates: dict[str, Environment] = {}
        for context in contexts:
            for environment in await self._repos.environments.list_for_owner(context):
                candidates[environment.id] = environment

        user_grantee = OwnerReference(OwnerKind.USER, user_id)
        for grantee in {user_grantee, *contexts}:
            for grant in await self._repos.grants.list_for_grantee(grantee):
                if grant.target_kind is GrantTargetKind.ENVIRONMENT:
                    environment = await self._repos.environments.get_by_id(grant.target_id)
                    if environment is not None:
                        candidates[environment.id] = environment
                elif grant.target_kind is GrantTargetKind.ALL:
                    for environment in await self._repos.environments.list_for_owner(grant.grantor):
                        candidates[environment.id] = environment

        usable = [
            environment
            for environment in candidates.values()
            if await self._usable_in_any_context(user_id, environment, contexts)
        ]
        return sorted(usable, key=lambda environment: (environment.name, environment.id))

    async def _usable_in_any_context(
        self,
        user_id: str,
        environment: Environment,
        contexts: list[OwnerReference],
    ) -> bool:
        for context in contexts:
            if (
                await environment_for_owner_use(self._repos, user_id, environment.id, context)
                is not None
            ):
                return True
        return False

    async def _views(self, environments: list[Environment], user_id: str) -> list[EnvironmentView]:
        owners = await owner_summaries(
            self._repos, (environment.owner for environment in environments)
        )
        return [
            EnvironmentView(
                environment=environment,
                versions=await self._repos.environments.list_versions(environment.id),
                owner=owners[(environment.owner.kind, environment.owner.id)],
                capabilities=await self._environment_capabilities(user_id, environment.id),
            )
            for environment in environments
        ]

    async def _environment_capabilities(
        self, user_id: str, environment_id: str
    ) -> frozenset[Capability]:
        try:
            access = await self._guard.environment(user_id, environment_id)
        except ObjectNotFound:
            return frozenset()
        return access.capabilities & {Capability.ENVIRONMENT_VERSION_CREATE}

    async def list_compute_plans(self) -> list[ComputePlan]:
        return await self._repos.compute_plans.list_all()
