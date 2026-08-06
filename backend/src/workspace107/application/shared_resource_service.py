"""Shared Resource 用例。

Shared Resource 是独立于 Project 存在的内容资源（设计稿 §2.6 / §3.1.3）：
数据集、预训练权重、语料库等。资源对象可变（名称、说明），
版本一旦发布即不可变（GR-201）。

可见性分两层（Core 子集）：

* Platform 持有（``owner_workspace_id is None``）——全平台可见，任意登录用户可读。
* Workspace 持有——成员可见；写入需要 ``SHARED_RESOURCE_MANAGE`` /
  ``SHARED_RESOURCE_VERSION_CREATE`` 能力。

跨 Workspace Asset Grant 在 M4 单独 Issue，本服务不实现。

文件内容存储复用 Project Version 已在用的 blob store——按内容寻址，
多个 Shared Resource Version 引用同一份内容不会重复占用空间。
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass

from ..domain import ids
from ..domain.capabilities import Capability
from ..domain.enums import ActivityAction, TargetType
from ..domain.errors import ObjectNotFound, PermissionDenied, ValidationFailed
from ..domain.models import (
    SharedResource,
    SharedResourceFile,
    SharedResourceVersion,
)
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from ..domain.ports.storage import StoragePort
from .access import AccessGuard, SharedResourceAccess
from .activity import ActivityRecorder

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

    async def list_platform(self, user_id: str) -> list[SharedResource]:
        """列出 Platform 持有的 Shared Resource。

        任意登录用户可读。当前 Core 子集不做资源搜索、预览（§2.6 V1）。
        """
        _ = user_id  # 校验已登录由路由层保证；这里没有额外权限门槛。
        return await self._repos.shared_resources.list_platform()

    async def list_for_workspace(self, user_id: str, workspace_id: str) -> list[SharedResource]:
        await self._guard.workspace(user_id, workspace_id, needs=Capability.SHARED_RESOURCE_VIEW)
        return await self._repos.shared_resources.list_for_workspace(workspace_id)

    async def get(self, user_id: str, resource_id: str) -> SharedResourceAccess:
        return await self._guard.shared_resource(user_id, resource_id)

    async def list_versions(self, user_id: str, resource_id: str) -> list[SharedResourceVersion]:
        await self._guard.shared_resource(user_id, resource_id)
        return await self._repos.shared_resources.list_versions(resource_id)

    async def get_version(
        self, user_id: str, version_id: str
    ) -> tuple[SharedResourceVersion, SharedResourceAccess]:
        return await self._guard.shared_resource_version(user_id, version_id)

    # -- 写入 -----------------------------------------------------------

    async def create(
        self,
        user_id: str,
        workspace_id: str,
        *,
        name: str,
        description: str = "",
    ) -> SharedResource:
        await self._guard.workspace(user_id, workspace_id, needs=Capability.SHARED_RESOURCE_MANAGE)
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
            description=description,
            owner_workspace_id=workspace_id,
            created_at=self._clock.now(),
        )
        await self._repos.shared_resources.add(resource)
        await self._activity.record(
            actor_id=user_id,
            workspace_id=workspace_id,
            action=ActivityAction.SHARED_RESOURCE_CREATED,
            target_type=TargetType.SHARED_RESOURCE,
            target_id=resource.id,
            target_name=resource.name,
        )
        return resource

    async def update(
        self,
        user_id: str,
        resource_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> SharedResource:
        access = await self._guard.shared_resource(
            user_id, resource_id, needs=Capability.SHARED_RESOURCE_MANAGE
        )
        resource = access.resource
        # Platform 资源当前 Core 子集不接受 API 改写——平台维护走运维通道。
        if resource.is_platform_owned:
            raise PermissionDenied("Platform 持有的资源由平台维护，当前不支持通过 API 修改")
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
        await self._activity.record(
            actor_id=user_id,
            workspace_id=resource.owner_workspace_id or "",
            action=ActivityAction.SHARED_RESOURCE_UPDATED,
            target_type=TargetType.SHARED_RESOURCE,
            target_id=resource.id,
            target_name=resource.name,
        )
        return resource

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
        if resource.is_platform_owned:
            raise PermissionDenied("Platform 持有的资源由平台维护，当前不支持通过 API 上传版本")
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
        await self._activity.record(
            actor_id=user_id,
            workspace_id=resource.owner_workspace_id or "",
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
