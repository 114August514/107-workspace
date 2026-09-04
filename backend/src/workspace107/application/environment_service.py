"""Environment publication use cases and authorization boundary."""

from __future__ import annotations

import hashlib

from ..domain import ids
from ..domain.capabilities import Capability
from ..domain.enums import EnvironmentPublicationStatus, EnvironmentRuntimeKind
from ..domain.errors import ObjectNotFound, ValidationFailed
from ..domain.models import EnvironmentPublicationAttempt, EnvironmentVersion
from ..domain.ownership import OwnerKind
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from ..domain.ports.storage import StoragePort
from .access import AccessGuard
from .environment_publication import EnvironmentPublicationProcessor


class EnvironmentPublicationService:
    def __init__(
        self, repos: Repositories, guard: AccessGuard, storage: StoragePort, clock: Clock
    ) -> None:
        self._repos = repos
        self._guard = guard
        self._storage = storage
        self._clock = clock

    async def create_modules(
        self,
        user_id: str,
        environment_id: str,
        *,
        version: str,
        description: str,
        modules: list[str],
    ) -> EnvironmentPublicationAttempt:
        await self._guard.environment(
            user_id, environment_id, needs=Capability.ENVIRONMENT_VERSION_CREATE
        )
        return await self._create(
            user_id,
            environment_id,
            version,
            description,
            EnvironmentRuntimeKind.MODULES,
            {"modules": modules},
        )

    async def create_sif(
        self,
        user_id: str,
        environment_id: str,
        *,
        version: str,
        description: str,
        content: bytes,
        source_uri: str,
        source_digest: str,
        architecture: str,
    ) -> EnvironmentPublicationAttempt:
        await self._guard.environment(
            user_id, environment_id, needs=Capability.ENVIRONMENT_VERSION_CREATE
        )
        if not content:
            raise ValidationFailed("SIF 文件不能为空")
        digest = hashlib.sha256(content).hexdigest()
        locator = await self._storage.write_blob(content)
        return await self._create(
            user_id,
            environment_id,
            version,
            description,
            EnvironmentRuntimeKind.APPTAINER_SIF,
            {
                "locator": locator,
                "sha256": digest,
                "size": len(content),
                "source_uri": source_uri,
                "source_digest": source_digest,
                "architecture": architecture,
            },
        )

    async def get(self, user_id: str, attempt_id: str) -> EnvironmentPublicationAttempt:
        attempt = await self._repos.environments.get_attempt_by_id(attempt_id)
        if attempt is None:
            raise ObjectNotFound("Environment Publication Attempt", attempt_id)
        await self._guard.environment(user_id, attempt.environment_id)
        return attempt

    async def list_attempts(
        self, user_id: str, environment_id: str
    ) -> list[EnvironmentPublicationAttempt]:
        await self._guard.environment(
            user_id, environment_id, needs=Capability.ENVIRONMENT_VERSION_CREATE
        )
        return await self._repos.environments.list_attempts_discoverable_for_user(
            user_id, environment_id
        )

    async def refresh_availability(self, user_id: str, version_id: str) -> EnvironmentVersion:
        version = await self._repos.environments.get_version_by_id(version_id)
        if version is None:
            raise ObjectNotFound("Environment Version", version_id)
        await self._guard.environment(
            user_id,
            version.environment_id,
            needs=Capability.ENVIRONMENT_VERSION_CREATE,
        )
        return await EnvironmentPublicationProcessor(
            self._repos, self._storage, self._clock
        ).refresh_availability(version.id)

    async def _create(
        self,
        user_id: str,
        environment_id: str,
        version: str,
        description: str,
        runtime_kind: EnvironmentRuntimeKind,
        candidate: dict[str, object],
    ) -> EnvironmentPublicationAttempt:
        version = version.strip()
        if not version:
            raise ValidationFailed("Environment 版本标签不能为空")
        if len(version) > 64:
            raise ValidationFailed("Environment 版本标签超过 64 个字符")
        environment = await self._repos.environments.get_by_id(environment_id)
        if environment is None:
            raise ObjectNotFound("Environment", environment_id)
        if (
            environment.owner.kind is OwnerKind.USER_GROUP
            and (await self._repos.user_groups.get_for_update(environment.owner.id)) is None
        ):
            raise ObjectNotFound("Environment", environment_id)
        attempt = EnvironmentPublicationAttempt(
            id=ids.new_id(ids.ENVIRONMENT_PUBLICATION_ATTEMPT),
            environment_id=environment_id,
            status=EnvironmentPublicationStatus.PENDING,
            version=version,
            description=description,
            runtime_kind=runtime_kind,
            candidate_definition=candidate,
            validation_summary="等待运行环境校验",
            validation_evidence={},
            failure_code=None,
            failure_reason=None,
            version_id=None,
            created_by=user_id,
            created_at=self._clock.now(),
        )
        await self._repos.environments.add_attempt(attempt)
        return attempt
