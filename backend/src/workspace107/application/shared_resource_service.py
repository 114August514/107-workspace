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
from ..domain.enums import ActivityAction, TargetType
from ..domain.errors import ObjectNotFound, PermissionDenied, ValidationFailed
from ..domain.models import (
    SharedResource,
    SharedResourceFile,
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


def _normalize_path(raw: str) -> str:
    """把用户传入的相对路径规范化。

    与 ProjectService.normalize_path 同语义：拒绝绝对路径和越出根目录的写法。
    """
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
    """一次上传意图。服务层据此把内容写入 blob store 并形成版本。"""

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

    async def list_actor_discoverable(self, user_id: str) -> list[SharedResourceView]:
        """Deprecated ``/catalog/shared-resources`` alias; no Platform semantics."""
        return await self.list_discoverable(user_id)

    async def list_for_workspace(self, user_id: str, workspace_id: str) -> list[SharedResourceView]:
        """Deprecated bounded adapter for one legacy Workspace ownership subject."""
        workspace_access = await self._guard.legacy_workspace(
            user_id, workspace_id, needs=Capability.SHARED_RESOURCE_VIEW
        )
        owner = workspace_access.workspace.owner_reference
        resources = [
            resource
            for resource in await self._repos.shared_resources.list_discoverable_for_user(user_id)
            if resource.owner == owner
        ]
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

    async def create_for_workspace(
        self,
        user_id: str,
        workspace_id: str,
        *,
        name: str,
        description: str = "",
    ) -> SharedResourceView:
        """Deprecated bounded adapter preserving the legacy payload."""
        workspace_access = await self._guard.legacy_workspace(
            user_id, workspace_id, needs=Capability.SHARED_RESOURCE_MANAGE
        )
        owner = workspace_access.workspace.owner_reference
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

    async def publish_version(
        self,
        user_id: str,
        resource_id: str,
        *,
        description: str,
        uploads: list[SharedResourceUpload],
    ) -> SharedResourceVersion:
        """上传文件并形成新的不可变版本。

        上传的文件先写入 blob store，再固化成 ``SharedResourceFile`` 列表。
        全部写完后才创建版本行——避免半成品版本残留在库中。
        """
        access = await self._guard.shared_resource(
            user_id, resource_id, needs=Capability.SHARED_RESOURCE_VERSION_CREATE
        )
        resource = access.resource
        activity_workspace_id = self._activity_user_group_id(resource.owner)
        if not uploads:
            raise ValidationFailed("版本必须至少包含一个文件")
        if len(description) > MAX_VERSION_DESCRIPTION_LEN:
            raise ValidationFailed(f"版本说明超过 {MAX_VERSION_DESCRIPTION_LEN} 个字符")

        # 先把所有文件落进 blob store，再写版本行。
        # 这样如果中间某个文件超限或路径非法，已经写入的 blob 也只是多占空间，
        # 不会留下一个半成品版本让数据库和活动流去解释。
        files: list[SharedResourceFile] = []
        seen_paths: set[str] = set()
        for upload in uploads:
            normalized = _normalize_path(upload.path)
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

        version = SharedResourceVersion(
            id=ids.new_id(ids.SHARED_RESOURCE_VERSION),
            shared_resource_id=resource_id,
            sequence=await self._repos.shared_resources.next_version_sequence(resource_id),
            description=description,
            files=tuple(files),
            created_by=user_id,
            created_at=self._clock.now(),
        )
        await self._repos.shared_resources.add_version(version)
        if activity_workspace_id is not None:
            await self._activity.record(
                actor_id=user_id,
                workspace_id=activity_workspace_id,
                action=ActivityAction.SHARED_RESOURCE_VERSION_PUBLISHED,
                target_type=TargetType.SHARED_RESOURCE_VERSION,
                target_id=version.id,
                target_name=f"{resource.name} · {version.label}",
                detail=version.description,
            )
        return version

    async def read_version_file(self, user_id: str, version_id: str, path: str) -> bytes:
        """读取版本中的文件内容（权限校验后从 blob store 取）。"""
        version, _ = await self._guard.shared_resource_version(user_id, version_id)
        normalized = _normalize_path(path)
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
