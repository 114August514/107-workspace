"""Shared Resource use cases with typed User/UserGroup ownership.

Resources are mutable metadata with immutable content versions (GR-201). Discovery is
repository-scoped to the exact User owner or active Membership of the owning UserGroup;
#40 may later add USE Grant discovery. Content storage continues to use the shared
content-addressed blob store.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass

from ..domain import ids
from ..domain.capabilities import Capability, capabilities_of, describe
from ..domain.enums import ActivityAction, SharedResourcePublicationStatus, TargetType
from ..domain.errors import ObjectNotFound, PermissionDenied, ValidationFailed
from ..domain.models import (
    SharedResource,
    SharedResourceFile,
    SharedResourcePublicationAttempt,
    SharedResourceVersion,
)
from ..domain.ownership import OwnerKind, OwnerReference
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from ..domain.ports.storage import StoragePort
from .access import AccessGuard, SharedResourceAccess
from .activity import ActivityRecorder
from .ownership import OwnerSummary, owner_summaries

MAX_RESOURCE_NAME_LEN = 128
MAX_RESOURCE_DESCRIPTION_LEN = 4096
MAX_VERSION_DESCRIPTION_LEN = 4096


def normalize_shared_resource_path(raw: str) -> str:
    """Normalize a candidate-relative path without allowing root escape."""
    candidate = raw.strip().replace("\\", "/").lstrip("/")
    if not candidate:
        raise ValidationFailed("路径不能为空")
    normalized = posixpath.normpath(candidate)
    if normalized in {".", ".."} or normalized.startswith("../"):
        raise ValidationFailed(f"路径 {raw!r} 越出了资源根目录")
    return normalized


@dataclass(frozen=True, slots=True)
class SharedResourceView:
    resource: SharedResource
    owner: OwnerSummary


@dataclass(frozen=True, slots=True)
class SharedResourceAccessView:
    access: SharedResourceAccess
    owner: OwnerSummary

    @property
    def resource(self) -> SharedResource:
        return self.access.resource


@dataclass(frozen=True, slots=True)
class SharedResourceUpload:
    """Candidate file received by the publication request."""

    path: str
    content: bytes


class SharedResourceService:
    def __init__(
        self,
        repos: Repositories,
        guard: AccessGuard,
        clock: Clock,
        storage: StoragePort,
        activity: ActivityRecorder,
        *,
        max_file_bytes: int,
    ) -> None:
        self._repos = repos
        self._guard = guard
        self._clock = clock
        self._storage = storage
        self._activity = activity
        self._max_file_bytes = max_file_bytes

    # -- 查询 -----------------------------------------------------------

    async def list_discoverable(self, user_id: str) -> list[SharedResourceView]:
        """Canonical actor-scoped list for ``GET /shared-resources``."""
        resources = await self._repos.shared_resources.list_discoverable_for_user(user_id)
        return await self._views(resources)

    async def get(self, user_id: str, resource_id: str) -> SharedResourceAccessView:
        access = await self._guard.shared_resource(user_id, resource_id)
        owner = await self._owner(access.resource.owner)
        return SharedResourceAccessView(access=access, owner=owner)

    async def list_versions(self, user_id: str, resource_id: str) -> list[SharedResourceVersion]:
        return await self._repos.shared_resources.list_versions_discoverable_for_user(
            user_id, resource_id
        )

    async def get_version(
        self, user_id: str, version_id: str
    ) -> tuple[SharedResourceVersion, SharedResourceAccess]:
        return await self._guard.shared_resource_version(user_id, version_id)

    async def get_publication_attempt(
        self, user_id: str, attempt_id: str
    ) -> SharedResourcePublicationAttempt:
        attempt = await self._repos.shared_resources.get_attempt_discoverable_for_user(
            user_id, attempt_id
        )
        if attempt is None:
            raise ObjectNotFound("Shared Resource Publication Attempt", attempt_id)
        return attempt

    # -- 写入 -----------------------------------------------------------

    async def create(
        self,
        user_id: str,
        *,
        owner: OwnerReference,
        name: str,
        description: str = "",
    ) -> SharedResourceView:
        """Canonical create with explicit legal owner.

        A User owner must be the actor; a UserGroup owner must exist and the actor
        must be an active member with ``SHARED_RESOURCE_MANAGE``. Cross-owner or
        unknown-owner attempts fail before any row is created.
        """
        await self._require_owner_authority(user_id, owner)
        resource = await self._create_with_owner(user_id, owner, name, description)
        return SharedResourceView(resource=resource, owner=await self._owner(resource.owner))

    async def update(
        self,
        user_id: str,
        resource_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> SharedResourceView:
        access = await self._guard.shared_resource(
            user_id, resource_id, needs=Capability.SHARED_RESOURCE_MANAGE
        )
        resource = access.resource
        activity_workspace_id = self._activity_user_group_id(resource.owner)
        if name is not None:
            name = name.strip()
            if not name:
                raise ValidationFailed("Shared Resource 名称不能为空")
            if len(name) > MAX_RESOURCE_NAME_LEN:
                raise ValidationFailed(f"Shared Resource 名称超过 {MAX_RESOURCE_NAME_LEN} 个字符")
            resource.name = name
        if description is not None:
            if len(description) > MAX_RESOURCE_DESCRIPTION_LEN:
                raise ValidationFailed(
                    f"Shared Resource 说明超过 {MAX_RESOURCE_DESCRIPTION_LEN} 个字符"
                )
            resource.description = description
        await self._repos.shared_resources.update(resource)
        if activity_workspace_id is not None:
            await self._activity.record(
                actor_id=user_id,
                workspace_id=activity_workspace_id,
                action=ActivityAction.SHARED_RESOURCE_UPDATED,
                target_type=TargetType.SHARED_RESOURCE,
                target_id=resource.id,
                target_name=resource.name,
            )
        return SharedResourceView(resource=resource, owner=await self._owner(resource.owner))

    async def create_publication_attempt(
        self,
        user_id: str,
        resource_id: str,
        *,
        description: str,
        uploads: list[SharedResourceUpload],
    ) -> SharedResourcePublicationAttempt:
        """Accept a transport-safe candidate for asynchronous integrity validation.

        Authorization plus path, duplicate-path, and size checks are ingress requirements:
        rejected raw requests never become publication attempts. Once accepted, the durable
        processor validates the persisted CAS blob existence, hash, and size before publishing.
        """
        await self._guard.shared_resource(
            user_id, resource_id, needs=Capability.SHARED_RESOURCE_VERSION_CREATE
        )
        if not uploads:
            raise ValidationFailed("版本必须至少包含一个文件")
        if len(description) > MAX_VERSION_DESCRIPTION_LEN:
            raise ValidationFailed(f"版本说明超过 {MAX_VERSION_DESCRIPTION_LEN} 个字符")

        files: list[SharedResourceFile] = []
        seen_paths: set[str] = set()
        for upload in uploads:
            normalized = normalize_shared_resource_path(upload.path)
            if normalized in seen_paths:
                raise ValidationFailed(f"版本中存在重复路径 {normalized!r}")
            if len(upload.content) > self._max_file_bytes:
                limit_mb = self._max_file_bytes // (1024 * 1024)
                raise ValidationFailed(f"文件 {normalized} 超过单个文件上限 {limit_mb} MB")
            content_hash = await self._storage.write_blob(upload.content)
            files.append(
                SharedResourceFile(
                    path=normalized,
                    size=len(upload.content),
                    content_hash=content_hash,
                )
            )
            seen_paths.add(normalized)

        attempt = SharedResourcePublicationAttempt(
            id=ids.new_id(ids.SHARED_RESOURCE_PUBLICATION_ATTEMPT),
            shared_resource_id=resource_id,
            status=SharedResourcePublicationStatus.PENDING,
            description=description,
            files=tuple(files),
            validation_summary="等待校验候选内容",
            failure_reason=None,
            version_id=None,
            created_by=user_id,
            created_at=self._clock.now(),
        )
        await self._repos.shared_resources.add_attempt(attempt)
        return attempt

    async def read_version_file(self, user_id: str, version_id: str, path: str) -> bytes:
        """读取版本中的文件内容（权限校验后从 blob store 取）。"""
        version, _ = await self._guard.shared_resource_version(user_id, version_id)
        normalized = normalize_shared_resource_path(path)
        for entry in version.files:
            if entry.path == normalized:
                return await self._storage.read_blob(entry.content_hash)
        raise ObjectNotFound("文件", normalized)

    async def _require_owner_authority(self, user_id: str, owner: OwnerReference) -> None:
        if owner.kind is OwnerKind.USER:
            if owner.id != user_id or await self._repos.users.get(owner.id) is None:
                raise ObjectNotFound("Owner", owner.id)
            return
        access = await self._guard.user_group(user_id, owner.id)
        role = access.role
        if Capability.SHARED_RESOURCE_MANAGE not in capabilities_of(role):
            raise PermissionDenied(
                f"当前角色（{role.value}）无权{describe(Capability.SHARED_RESOURCE_MANAGE)}"
            )

    async def _create_with_owner(
        self,
        user_id: str,
        owner: OwnerReference,
        name: str,
        description: str,
    ) -> SharedResource:
        name = name.strip()
        if not name:
            raise ValidationFailed("Shared Resource 名称不能为空")
        if len(name) > MAX_RESOURCE_NAME_LEN:
            raise ValidationFailed(f"Shared Resource 名称超过 {MAX_RESOURCE_NAME_LEN} 个字符")
        if len(description) > MAX_RESOURCE_DESCRIPTION_LEN:
            raise ValidationFailed(
                f"Shared Resource 说明超过 {MAX_RESOURCE_DESCRIPTION_LEN} 个字符"
            )

        resource = SharedResource(
            id=ids.new_id(ids.SHARED_RESOURCE),
            name=name,
            owner=owner,
            description=description,
            created_at=self._clock.now(),
        )
        await self._repos.shared_resources.add(resource)
        activity_workspace_id = self._activity_user_group_id(owner)
        if activity_workspace_id is not None:
            await self._activity.record(
                actor_id=user_id,
                workspace_id=activity_workspace_id,
                action=ActivityAction.SHARED_RESOURCE_CREATED,
                target_type=TargetType.SHARED_RESOURCE,
                target_id=resource.id,
                target_name=resource.name,
            )
        return resource

    @staticmethod
    def _activity_user_group_id(owner: OwnerReference) -> str | None:
        """Activity is UserGroup-scoped; User-owned assets have no fake Workspace feed."""
        return owner.id if owner.kind is OwnerKind.USER_GROUP else None

    async def _views(self, resources: list[SharedResource]) -> list[SharedResourceView]:
        owners = await owner_summaries(self._repos, (resource.owner for resource in resources))
        return [
            SharedResourceView(
                resource=resource,
                owner=owners[(resource.owner.kind, resource.owner.id)],
            )
            for resource in resources
        ]

    async def _owner(self, owner: OwnerReference) -> OwnerSummary:
        return (await owner_summaries(self._repos, (owner,)))[(owner.kind, owner.id)]
