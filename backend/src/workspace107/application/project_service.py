"""Project、项目文件与版本用例。

Project Working State 可变，Project Version 不可变（GR-201）。
保存版本时对当前内容形成快照；恢复历史版本是把快照内容写回工作区，
不会改变那个历史版本本身。
"""

from __future__ import annotations

import io
import posixpath
import re
import stat
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass

from ..domain import ids
from ..domain.capabilities import Capability, capabilities_of, describe
from ..domain.enums import (
    ActivityAction,
    ChangeKind,
    InputSourceType,
    ProjectStatus,
    ProjectVisibility,
    TargetType,
)
from ..domain.errors import (
    ConflictError,
    ObjectNotFound,
    PermissionDenied,
    ValidationFailed,
)
from ..domain.models import (
    ForkRelation,
    Project,
    ProjectFile,
    ProjectVersion,
    ProjectVersionFile,
    RunConfiguration,
)
from ..domain.ownership import OwnerKind, OwnerReference
from ..domain.pagination import Page, PageRequest
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from ..domain.ports.storage import StoragePort
from .access import AccessGuard, ProjectAccess
from .activity import ActivityRecorder
from .asset_use import (
    environment_version_for_owner_use,
    shared_resource_version_for_owner_use,
)
from .ownership import OwnerSummary
from .ownership import owner_summaries as resolve_owner_summaries

MAX_INLINE_PREVIEW_BYTES = 512 * 1024

# 压缩包展开预算的默认值；组合根会用配置覆盖。
DEFAULT_MAX_ARCHIVE_TOTAL_BYTES = 128 * 1024 * 1024
DEFAULT_MAX_ARCHIVE_ENTRIES = 500


def normalize_path(raw: str) -> str:
    """把用户传入的路径规范化为仓库内相对路径。

    拒绝绝对路径和任何越出项目根目录的写法。
    """
    candidate = raw.strip().replace("\\", "/").lstrip("/")
    if not candidate:
        raise ValidationFailed("路径不能为空")
    normalized = posixpath.normpath(candidate)
    if normalized in {".", ".."} or normalized.startswith("../"):
        raise ValidationFailed(f"路径 {raw!r} 越出了项目根目录")
    return normalized


def _validate_file_namespace(
    existing_paths: Iterable[str],
    proposed_paths: Iterable[str],
    *,
    removed_paths: Iterable[str] = (),
) -> None:
    """Ensure the resulting file set has no file/directory name collisions."""
    proposed = list(proposed_paths)
    if len(proposed) != len(set(proposed)):
        raise ConflictError("目标中有多个文件规范化为同一路径")

    final_paths = set(existing_paths)
    final_paths.difference_update(removed_paths)
    final_paths.update(proposed)
    for path in sorted(final_paths):
        parts = path.split("/")
        for index in range(1, len(parts)):
            ancestor = "/".join(parts[:index])
            if ancestor in final_paths:
                raise ConflictError(f"「{ancestor}」已是文件，不能同时作为目录")


@dataclass(frozen=True, slots=True)
class VersionDiffEntry:
    path: str
    change: ChangeKind


@dataclass(frozen=True, slots=True)
class WorkingTreeChange:
    path: str
    change: ChangeKind


@dataclass(frozen=True, slots=True)
class WorkingChangeDetail:
    """一个未保存变更的两侧内容事实，由路由层负责预览截断与解码。"""

    path: str
    change: ChangeKind
    previous: bytes | None
    """基线（最近保存版本）中的内容；新增时为空。"""
    current: bytes | None
    """当前工作区内容；删除时为空。"""


class ProjectService:
    def __init__(
        self,
        repos: Repositories,
        guard: AccessGuard,
        clock: Clock,
        storage: StoragePort,
        activity: ActivityRecorder,
        *,
        max_file_bytes: int,
        max_archive_total_bytes: int = DEFAULT_MAX_ARCHIVE_TOTAL_BYTES,
        max_archive_entries: int = DEFAULT_MAX_ARCHIVE_ENTRIES,
    ) -> None:
        self._repos = repos
        self._guard = guard
        self._clock = clock
        self._storage = storage
        self._activity = activity
        # 上限从组合根注入而不是读全局配置：用例的依赖都写在构造函数上，
        # 测试要换一个小上限也不用改环境变量。
        self._max_file_bytes = max_file_bytes
        self._max_archive_total_bytes = max_archive_total_bytes
        self._max_archive_entries = max_archive_entries

    # -- Project --------------------------------------------------------

    async def list_recent_for_user(self, user_id: str, *, limit: int = 10) -> list[Project]:
        return await self._repos.projects.list_for_user(user_id, limit=limit)

    async def list_discoverable_for_user(self, user_id: str, page: PageRequest) -> Page[Project]:
        return await self._repos.projects.list_discoverable_for_user(user_id, page)

    async def get(self, user_id: str, project_id: str) -> ProjectAccess:
        return await self._guard.project(user_id, project_id)

    async def create_owned(
        self,
        user_id: str,
        owner: OwnerReference,
        name: str,
        description: str = "",
        *,
        visibility: ProjectVisibility = ProjectVisibility.OWNER_SCOPE,
    ) -> Project:
        """Create a Project under one explicit current User/UserGroup owner."""
        await self._require_owner_create(user_id, owner)
        name = name.strip()
        if not name:
            raise ValidationFailed("Project 名称不能为空")
        if await self._repos.projects.name_exists(owner, name):
            raise ConflictError(f"当前 Owner 中已存在名为「{name}」的 Project")

        now = self._clock.now()
        project = Project(
            id=ids.new_id(ids.PROJECT),
            name=name,
            owner=owner,
            description=description,
            visibility=visibility,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        await self._repos.projects.add(project)
        await self._activity.record(
            actor_id=user_id,
            owner=owner,
            project_id=project.id,
            action=ActivityAction.PROJECT_CREATED,
            target_type=TargetType.PROJECT,
            target_id=project.id,
            target_name=project.name,
        )
        return project

    async def _require_owner_create(self, user_id: str, owner: OwnerReference) -> None:
        if owner.kind is OwnerKind.USER:
            if owner.id != user_id or await self._repos.users.get(owner.id) is None:
                raise ObjectNotFound("Project Owner", owner.id)
            return
        access = await self._guard.user_group(user_id, owner.id)
        if Capability.PROJECT_CREATE not in capabilities_of(access.role):
            raise PermissionDenied(
                f"当前角色（{access.role.value}）无权{describe(Capability.PROJECT_CREATE)}"
            )

    async def owner_summary(self, project: Project) -> OwnerSummary:
        summaries = await resolve_owner_summaries(self._repos, [project.owner])
        return summaries[(project.owner.kind, project.owner.id)]

    async def owner_summaries(
        self, projects: list[Project]
    ) -> dict[tuple[OwnerKind, str], OwnerSummary]:
        return await resolve_owner_summaries(self._repos, [p.owner for p in projects])

    async def update(
        self,
        user_id: str,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        environment_version_id: str | None = None,
        update_environment_version: bool = False,
        default_run_configuration_id: str | None = None,
        visibility: ProjectVisibility | None = None,
    ) -> Project:
        access = await self._guard.project(user_id, project_id, needs=Capability.PROJECT_UPDATE)
        project = access.project

        if name is not None:
            name = name.strip()
            if not name:
                raise ValidationFailed("Project 名称不能为空")
            if name != project.name and await self._repos.projects.name_exists(project.owner, name):
                raise ConflictError(f"当前 Owner 中已存在名为「{name}」的 Project")
            project.name = name
        if description is not None:
            project.description = description
        if visibility is not None:
            project.visibility = visibility
        if update_environment_version:
            if environment_version_id is None:
                project.environment_version_id = None
            else:
                version = await environment_version_for_owner_use(
                    self._repos,
                    user_id,
                    environment_version_id,
                    project.owner,
                )
                if version is None:
                    raise ObjectNotFound("Environment Version", environment_version_id)
                project.environment_version_id = version.id
        if default_run_configuration_id is not None:
            configuration = await self._repos.run_configurations.get(default_run_configuration_id)
            if configuration is None or configuration.project_id != project.id:
                raise ObjectNotFound("Run Configuration", default_run_configuration_id)
            project.default_run_configuration_id = configuration.id

        project.updated_at = self._clock.now()
        await self._repos.projects.update(project)
        await self._activity.record(
            actor_id=user_id,
            owner=project.owner,
            project_id=project.id,
            action=ActivityAction.PROJECT_UPDATED,
            target_type=TargetType.PROJECT,
            target_id=project.id,
            target_name=project.name,
        )
        return project

    async def set_status(self, user_id: str, project_id: str, status: ProjectStatus) -> Project:
        access = await self._guard.project(user_id, project_id, needs=Capability.PROJECT_UPDATE)
        access.project.status = status
        access.project.updated_at = self._clock.now()
        await self._repos.projects.update(access.project)
        return access.project

    # -- 文件 -----------------------------------------------------------

    async def list_files(self, user_id: str, project_id: str) -> list[ProjectFile]:
        await self._guard.project(user_id, project_id, owner_scope=True)
        files = await self._repos.project_files.list_for_project(project_id)
        return sorted(files, key=lambda f: f.path)

    async def read_file(self, user_id: str, project_id: str, path: str) -> bytes:
        await self._guard.project(user_id, project_id, owner_scope=True)
        normalized = normalize_path(path)
        record = await self._repos.project_files.get(project_id, normalized)
        if record is None:
            raise ObjectNotFound("文件", normalized)
        return await self._storage.read_blob(record.content_hash)

    async def write_file(
        self, user_id: str, project_id: str, path: str, content: bytes
    ) -> ProjectFile:
        access = await self._guard.project(
            user_id, project_id, needs=Capability.PROJECT_CONTENT_WRITE
        )
        normalized = normalize_path(path)
        existing = await self._repos.project_files.list_for_project(project_id)
        _validate_file_namespace((file.path for file in existing), [normalized])
        record = await self._store_entry(project_id, normalized, content)
        await self._touch(access.project)
        return record

    async def _store_entry(self, project_id: str, path: str, content: bytes) -> ProjectFile:
        """写入单个文件条目：上限校验、内容寻址存储、元数据 upsert。

        鉴权和刷新项目修改时间由调用方负责；批量写入时只 touch 一次。
        """
        # 中间件按 Content-Length 挡掉的是明显超大的请求，
        # 但那个头可能缺失或被伪造，所以真正的上限在这里再判一次。
        if len(content) > self._max_file_bytes:
            limit_mb = self._max_file_bytes // (1024 * 1024)
            raise ValidationFailed(
                f"文件 {path} 超过单个文件上限 {limit_mb} MB。"
                "大数据集和模型权重应当作为共享资源管理，不要放进 Project 文件。"
            )

        content_hash = await self._storage.write_blob(content)

        record = ProjectFile(
            project_id=project_id,
            path=path,
            size=len(content),
            content_hash=content_hash,
            updated_at=self._clock.now(),
        )
        await self._repos.project_files.upsert(record)
        return record

    async def delete_path(self, user_id: str, project_id: str, path: str) -> int:
        """删除一个文件或整个目录，返回删除的文件数量。"""
        access = await self._guard.project(
            user_id, project_id, needs=Capability.PROJECT_CONTENT_WRITE
        )
        normalized = normalize_path(path)

        record = await self._repos.project_files.get(project_id, normalized)
        if record is not None:
            await self._repos.project_files.delete(project_id, normalized)
            await self._touch(access.project)
            return 1

        removed = await self._repos.project_files.delete_under(project_id, normalized + "/")
        if removed == 0:
            raise ObjectNotFound("文件或目录", normalized)
        await self._touch(access.project)
        return removed

    async def move_path(
        self, user_id: str, project_id: str, source: str, destination: str
    ) -> list[ProjectFile]:
        """移动或重命名文件 / 目录。"""
        access = await self._guard.project(
            user_id, project_id, needs=Capability.PROJECT_CONTENT_WRITE
        )
        src = normalize_path(source)
        dst = normalize_path(destination)
        if src == dst:
            raise ValidationFailed("源路径和目标路径相同")
        if dst.startswith(src + "/"):
            raise ValidationFailed("不能把目录移动到自己的子目录中")

        existing = await self._repos.project_files.list_for_project(project_id)
        matched = [f for f in existing if f.path == src or f.path.startswith(src + "/")]
        if not matched:
            raise ObjectNotFound("文件或目录", src)
        proposed: list[tuple[ProjectFile, str]] = []
        for file in matched:
            suffix = file.path[len(src) :]
            proposed.append((file, dst + suffix))
        _validate_file_namespace(
            (file.path for file in existing),
            (new_path for _, new_path in proposed),
            removed_paths=(file.path for file in matched),
        )

        moved: list[ProjectFile] = []
        now = self._clock.now()
        for file, new_path in proposed:
            await self._repos.project_files.delete(project_id, file.path)
            record = ProjectFile(
                project_id=project_id,
                path=new_path,
                size=file.size,
                content_hash=file.content_hash,
                updated_at=now,
            )
            await self._repos.project_files.upsert(record)
            moved.append(record)

        await self._touch(access.project)
        return moved

    async def copy_path(
        self, user_id: str, project_id: str, source: str, destination: str
    ) -> list[ProjectFile]:
        """复制文件或目录，返回复制出的文件。

        内容按摘要寻址，复制只新增元数据行、不搬运字节；目标已存在的
        同路径文件会被覆盖。
        """
        access = await self._guard.project(
            user_id, project_id, needs=Capability.PROJECT_CONTENT_WRITE
        )
        src = normalize_path(source)
        dst = normalize_path(destination)
        if src == dst:
            raise ValidationFailed("源路径和目标路径相同")
        if dst.startswith(src + "/"):
            raise ValidationFailed("不能把目录复制到自己的子目录中")

        existing = await self._repos.project_files.list_for_project(project_id)
        matched = [f for f in existing if f.path == src or f.path.startswith(src + "/")]
        if not matched:
            raise ObjectNotFound("文件或目录", src)
        proposed = [(file, dst + file.path[len(src) :]) for file in matched]
        _validate_file_namespace(
            (file.path for file in existing),
            (new_path for _, new_path in proposed),
        )

        copied: list[ProjectFile] = []
        now = self._clock.now()
        for file, new_path in proposed:
            record = ProjectFile(
                project_id=project_id,
                path=new_path,
                size=file.size,
                content_hash=file.content_hash,
                updated_at=now,
            )
            await self._repos.project_files.upsert(record)
            copied.append(record)

        await self._touch(access.project)
        return copied

    async def create_directory(self, user_id: str, project_id: str, path: str) -> ProjectFile:
        """创建目录。

        目录本身不是实体，靠其中文件的路径前缀存在；这里写入一个
        ``.gitkeep`` 占位文件，让空目录在文件列表里可见、能保存进版本。
        """
        access = await self._guard.project(
            user_id, project_id, needs=Capability.PROJECT_CONTENT_WRITE
        )
        normalized = normalize_path(path)
        existing = await self._repos.project_files.list_for_project(project_id)
        placeholder = f"{normalized}/.gitkeep"
        _validate_file_namespace((file.path for file in existing), [placeholder])

        record = await self._store_entry(project_id, placeholder, b"")
        await self._touch(access.project)
        return record

    async def upload_archive(
        self, user_id: str, project_id: str, filename: str, data: bytes, *, prefix: str = ""
    ) -> list[ProjectFile]:
        """上传并展开 zip 压缩包到工作区，返回写入的文件。

        展开前逐条目校验（见 :meth:`_extract_archive`），全部校验通过才
        开始写入；同路径文件会被覆盖。
        """
        access = await self._guard.project(
            user_id, project_id, needs=Capability.PROJECT_CONTENT_WRITE
        )
        normalized_prefix = normalize_path(prefix) if prefix.strip() else ""
        entries = self._extract_archive(filename, data)
        target_entries = [
            (
                f"{normalized_prefix}/{relative_path}" if normalized_prefix else relative_path,
                payload,
            )
            for relative_path, payload in entries
        ]
        existing = await self._repos.project_files.list_for_project(project_id)
        _validate_file_namespace(
            (file.path for file in existing),
            (target for target, _ in target_entries),
        )

        written: list[ProjectFile] = []
        for target, payload in target_entries:
            written.append(await self._store_entry(project_id, target, payload))
        await self._touch(access.project)
        return written

    def _extract_archive(self, filename: str, data: bytes) -> list[tuple[str, bytes]]:
        """把压缩包安全展开成 ``(相对路径, 内容)`` 列表。

        只支持 zip。逐条目拒绝路径穿越（经 :func:`normalize_path`）、绝对
        路径、符号链接和加密条目；按声明的条目数和解压后总大小设预算，
        防止 zip 炸弹。原始请求体的大小由请求体中间件负责。任何条目不
        合法就整体拒绝——不做部分展开。
        """
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise ValidationFailed(f"「{filename}」不是有效的 zip 压缩包") from exc

        with archive:
            members: list[tuple[zipfile.ZipInfo, str]] = []
            total_uncompressed = 0
            for info in archive.infolist():
                raw_name = info.filename
                if raw_name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", raw_name):
                    raise ValidationFailed(f"压缩包包含绝对路径条目「{raw_name}」，已拒绝展开")

                name = raw_name.replace("\\", "/")
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise ValidationFailed(f"压缩包包含符号链接条目「{name}」，已拒绝展开")
                if info.flag_bits & 0x1:
                    raise ValidationFailed(f"压缩包包含加密条目「{name}」，不支持展开")
                if info.is_dir():
                    continue

                normalized = normalize_path(name)
                if info.file_size > self._max_file_bytes:
                    limit_mb = self._max_file_bytes // (1024 * 1024)
                    raise ValidationFailed(f"压缩包内的「{name}」超过单个文件上限 {limit_mb} MB")
                total_uncompressed += info.file_size
                if total_uncompressed > self._max_archive_total_bytes:
                    limit_mb = self._max_archive_total_bytes // (1024 * 1024)
                    raise ValidationFailed(f"压缩包解压后超过总大小上限 {limit_mb} MB")
                members.append((info, normalized))

            if not members:
                raise ValidationFailed(f"压缩包「{filename}」中没有可展开的文件")
            if len(members) > self._max_archive_entries:
                raise ValidationFailed(
                    f"压缩包含有 {len(members)} 个文件，超过 {self._max_archive_entries} 个的上限"
                )
            _validate_file_namespace((), (name for _, name in members))

            entries: list[tuple[str, bytes]] = []
            for info, name in members:
                # 声明大小之外再多读一个字节：头部谎报大小时在这里暴露，
                # 内存占用也始终有界。
                with archive.open(info) as member:
                    payload = member.read(self._max_file_bytes + 1)
                if len(payload) != info.file_size:
                    raise ValidationFailed(
                        f"压缩包内的「{name}」实际内容与声明大小不符，已拒绝展开"
                    )
                entries.append((name, payload))
            return entries

    async def download_file(self, user_id: str, project_id: str, path: str) -> tuple[str, bytes]:
        """读取完整文件用于下载，返回 ``(文件名, 内容字节)``。"""
        await self._guard.project(user_id, project_id, owner_scope=True)
        normalized = normalize_path(path)
        record = await self._repos.project_files.get(project_id, normalized)
        if record is None:
            raise ObjectNotFound("文件", normalized)
        return posixpath.basename(record.path), await self._storage.read_blob(record.content_hash)

    # -- 版本 -----------------------------------------------------------

    async def list_versions(
        self, user_id: str, project_id: str, page: PageRequest
    ) -> Page[ProjectVersion]:
        await self._guard.project(user_id, project_id)
        return await self._repos.project_versions.list_for_project(project_id, page)

    async def get_version(self, user_id: str, version_id: str) -> ProjectVersion:
        version = await self._repos.project_versions.get(version_id)
        if version is None:
            raise ObjectNotFound("Project Version", version_id)
        try:
            await self._guard.project(user_id, version.project_id)
        except ObjectNotFound as exc:
            raise ObjectNotFound("Project Version", version_id) from exc
        return version

    async def working_changes(self, user_id: str, project_id: str) -> list[WorkingTreeChange]:
        """查看当前未保存的文件变更：工作区与最近一个版本的差异。"""
        await self._guard.project(user_id, project_id, owner_scope=True)
        latest = await self._repos.project_versions.latest(project_id)
        baseline = {f.path: f.content_hash for f in latest.files} if latest else {}
        current = {
            f.path: f.content_hash
            for f in await self._repos.project_files.list_for_project(project_id)
        }
        return [
            WorkingTreeChange(path=path, change=change) for path, change in _diff(baseline, current)
        ]

    async def working_change_detail(
        self, user_id: str, project_id: str, path: str
    ) -> WorkingChangeDetail:
        """查看一个未保存变更的内容级详情：基线内容与工作区内容。"""
        await self._guard.project(user_id, project_id, owner_scope=True)
        normalized = normalize_path(path)

        latest = await self._repos.project_versions.latest(project_id)
        baseline = {f.path: f for f in latest.files} if latest else {}
        files = await self._repos.project_files.list_for_project(project_id)
        current = {f.path: f for f in files}

        previous_hash = baseline[normalized].content_hash if normalized in baseline else None
        current_hash = current[normalized].content_hash if normalized in current else None
        if previous_hash == current_hash:
            raise ObjectNotFound("未保存变更", normalized)

        return WorkingChangeDetail(
            path=normalized,
            change=_change_kind(previous_hash, current_hash),
            previous=await self._storage.read_blob(previous_hash) if previous_hash else None,
            current=await self._storage.read_blob(current_hash) if current_hash else None,
        )

    async def discard_changes(
        self, user_id: str, project_id: str, paths: list[str]
    ) -> list[WorkingTreeChange]:
        """放弃指定的未保存变更，把工作区恢复到最近版本对应的内容。

        只影响 Working State，历史版本不动（GR-201）。没有待放弃变化的
        路径按幂等处理、直接跳过；返回剩余的未保存变更。
        """
        access = await self._guard.project(
            user_id, project_id, needs=Capability.PROJECT_CONTENT_WRITE
        )
        normalized_paths: list[str] = []
        seen: set[str] = set()
        for raw in paths:
            normalized = normalize_path(raw)
            if normalized not in seen:
                seen.add(normalized)
                normalized_paths.append(normalized)

        latest = await self._repos.project_versions.latest(project_id)
        baseline = {f.path: f for f in latest.files} if latest else {}
        pending_hashes = {
            f.path: f.content_hash
            for f in await self._repos.project_files.list_for_project(project_id)
        }
        pending = dict(_diff({p: f.content_hash for p, f in baseline.items()}, pending_hashes))
        resulting_paths = set(pending_hashes)
        for path in normalized_paths:
            change = pending.get(path)
            if change is ChangeKind.ADDED:
                resulting_paths.discard(path)
            elif change is not None:
                resulting_paths.add(path)
        _validate_file_namespace((), resulting_paths)

        now = self._clock.now()
        discarded = False
        for path in normalized_paths:
            change = pending.get(path)
            if change is None:
                continue
            if change is ChangeKind.ADDED:
                await self._repos.project_files.delete(project_id, path)
            else:
                # MODIFIED 用基线内容覆盖回去，REMOVED 按基线重建；
                # 两者都是复用基线条目的内容摘要，不写新 blob。
                entry = baseline[path]
                await self._repos.project_files.upsert(
                    ProjectFile(
                        project_id=project_id,
                        path=path,
                        size=entry.size,
                        content_hash=entry.content_hash,
                        updated_at=now,
                    )
                )
            discarded = True

        if discarded:
            await self._touch(access.project)

        remaining_current = {
            f.path: f.content_hash
            for f in await self._repos.project_files.list_for_project(project_id)
        }
        return [
            WorkingTreeChange(path=path, change=change)
            for path, change in _diff(
                {p: f.content_hash for p, f in baseline.items()}, remaining_current
            )
        ]

    async def save_version(self, user_id: str, project_id: str, message: str) -> ProjectVersion:
        access = await self._guard.project(
            user_id, project_id, needs=Capability.PROJECT_CONTENT_WRITE
        )
        files = await self._repos.project_files.list_for_project(project_id)
        if not files:
            raise ValidationFailed("Project 中没有文件，无法保存版本")

        latest = await self._repos.project_versions.latest(project_id)
        if latest is not None:
            baseline = {f.path: f.content_hash for f in latest.files}
            current = {f.path: f.content_hash for f in files}
            if baseline == current:
                raise ConflictError("当前内容与最近一个版本相同，没有需要保存的变更")

        version = ProjectVersion(
            id=ids.new_id(ids.PROJECT_VERSION),
            project_id=project_id,
            sequence=await self._repos.project_versions.next_sequence(project_id),
            message=message.strip() or "保存版本",
            files=tuple(
                ProjectVersionFile(path=f.path, size=f.size, content_hash=f.content_hash)
                for f in sorted(files, key=lambda f: f.path)
            ),
            created_by=user_id,
            created_at=self._clock.now(),
        )
        await self._repos.project_versions.add(version)
        await self._touch(access.project)
        await self._activity.record(
            actor_id=user_id,
            owner=access.project.owner,
            project_id=project_id,
            action=ActivityAction.VERSION_SAVED,
            target_type=TargetType.PROJECT_VERSION,
            target_id=version.id,
            target_name=f"v{version.sequence}",
            detail=version.message,
        )
        return version

    async def diff_versions(
        self, user_id: str, base_version_id: str, target_version_id: str
    ) -> list[VersionDiffEntry]:
        base = await self.get_version(user_id, base_version_id)
        target = await self.get_version(user_id, target_version_id)
        if base.project_id != target.project_id:
            raise ValidationFailed("只能比较同一个 Project 的两个版本")

        left = {f.path: f.content_hash for f in base.files}
        right = {f.path: f.content_hash for f in target.files}
        return [VersionDiffEntry(path=path, change=change) for path, change in _diff(left, right)]

    async def restore_version(self, user_id: str, version_id: str) -> list[ProjectFile]:
        """把工作区恢复到指定历史版本。

        这是对可变 Working State 的写操作；历史版本本身不受影响（GR-204）。
        """
        version = await self.get_version(user_id, version_id)
        access = await self._guard.project(
            user_id, version.project_id, needs=Capability.PROJECT_CONTENT_WRITE
        )

        for file in await self._repos.project_files.list_for_project(version.project_id):
            await self._repos.project_files.delete(version.project_id, file.path)

        now = self._clock.now()
        restored: list[ProjectFile] = []
        for entry in version.files:
            record = ProjectFile(
                project_id=version.project_id,
                path=entry.path,
                size=entry.size,
                content_hash=entry.content_hash,
                updated_at=now,
            )
            await self._repos.project_files.upsert(record)
            restored.append(record)

        await self._touch(access.project)
        await self._activity.record(
            actor_id=user_id,
            owner=access.project.owner,
            project_id=version.project_id,
            action=ActivityAction.VERSION_RESTORED,
            target_type=TargetType.PROJECT_VERSION,
            target_id=version.id,
            target_name=f"v{version.sequence}",
        )
        return restored

    async def read_version_file(self, user_id: str, version_id: str, path: str) -> bytes:
        version = await self.get_version(user_id, version_id)
        normalized = normalize_path(path)
        for entry in version.files:
            if entry.path == normalized:
                return await self._storage.read_blob(entry.content_hash)
        raise ObjectNotFound("文件", normalized)

    # -- 内部 -----------------------------------------------------------

    async def fork(
        self,
        user_id: str,
        version_id: str,
        target_owner: OwnerReference,
        *,
        name: str = "",
        description: str = "",
    ) -> Project:
        """从一个确定版本派生出新 Project。

        产生的是**新 Project**，不是源 Project 的分支（设计稿 §3.4.2）。
        新 Project 归目标 Owner，从此和源 Project 没有任何持续关系（GR-502）。

        两侧都要校验：源版本可读、目标 Owner 下可创建。少任何一边都是越权——
        只查源就等于「谁都能往别人空间里塞项目」，只查目标就等于
        「Fork 一下就能读到看不见的内容」。

        复制什么、不复制什么见 GR-503，下面按顺序标注了。
        **权益、凭据、成员权限、Run 历史一律不复制**——那些属于源 Owner，
        跟着复制过来就是越权。

        PUBLIC 读者只能 Fork 出只含文件与不可变版本的新 Project：不读取、不验证、
        不复制源 Project 的 mutable environment selection、Run Configuration、Secret。
        Secret values are never copied; target exact scopes are re-resolved at preflight.
        """
        # 1. 源版本可读
        source_version = await self.get_version(user_id, version_id)
        source_access = await self._guard.project(
            user_id, source_version.project_id, needs=Capability.PROJECT_VIEW
        )

        # 2. 目标 Owner / 空间可写
        owner = target_owner
        await self._require_owner_create(user_id, owner)

        name = (name or source_access.project.name).strip()
        if not name:
            raise ValidationFailed("Project 名称不能为空")
        if await self._repos.projects.name_exists(owner, name):
            raise ConflictError(f"当前 Owner 中已存在名为「{name}」的 Project")

        configurations: list[RunConfiguration]
        if source_access.owner_scope:
            # Owner-scope forker: 读取并按目标 Owner 做 grant-aware 校验后复制。
            project_environment_id = source_access.project.environment_version_id
            if (
                project_environment_id is not None
                and await environment_version_for_owner_use(
                    self._repos, user_id, project_environment_id, owner
                )
                is None
            ):
                raise ObjectNotFound("Environment Version", project_environment_id)

            configurations = await self._repos.run_configurations.list_for_project(
                source_version.project_id
            )
            for configuration in configurations:
                # 运行方案精确引用 Environment Version（#41），逐个按目标 Owner 校验。
                if (
                    await environment_version_for_owner_use(
                        self._repos, user_id, configuration.environment_version_id, owner
                    )
                    is None
                ):
                    raise ObjectNotFound(
                        "Environment Version", configuration.environment_version_id
                    )
                for binding in configuration.input_bindings:
                    if (
                        binding.source_type is InputSourceType.SHARED_RESOURCE_VERSION
                        and await shared_resource_version_for_owner_use(
                            self._repos, user_id, binding.source_id, owner
                        )
                        is None
                    ):
                        raise ObjectNotFound("Shared Resource Version", binding.source_id)
                    if binding.source_type is InputSourceType.ARTIFACT:
                        artifact = await self._repos.artifacts.get(binding.source_id)
                        artifact_project = (
                            await self._repos.projects.get(artifact.project_id)
                            if artifact is not None
                            else None
                        )
                        if artifact_project is None or artifact_project.owner != owner:
                            raise ObjectNotFound("Artifact", binding.source_id)
        else:
            # PUBLIC 读者：根本不进入受保护配置的读取路径。
            project_environment_id = None
            configurations = []

        now = self._clock.now()
        project = Project(
            id=ids.new_id(ids.PROJECT),
            name=name,
            owner=owner,
            description=description or source_access.project.description,
            # Asset references were validated against the target owner before any writes
            # (owner-scope path). PUBLIC forkers carry no mutable references.
            environment_version_id=project_environment_id,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        await self._repos.projects.add(project)

        # 3. 内容：只复制 (path, size, content_hash)，一个字节都不搬。
        #    存储是按内容寻址的，几十 GB 的数据集 Fork 一百次也只占一份。
        for entry in source_version.files:
            await self._repos.project_files.upsert(
                ProjectFile(
                    project_id=project.id,
                    path=entry.path,
                    size=entry.size,
                    content_hash=entry.content_hash,
                    updated_at=now,
                )
            )

        # 工作区和一个起始版本都要有：只给版本的话页面上看不到文件，
        # 只给工作区的话没有版本可跑，提交前检查会直接拦下。
        await self._repos.project_versions.add(
            ProjectVersion(
                id=ids.new_id(ids.PROJECT_VERSION),
                project_id=project.id,
                sequence=1,
                message=(f"Fork 自 {source_access.project.name} 的 {source_version.label}"),
                files=source_version.files,
                created_by=user_id,
                created_at=now,
            )
        )

        # 4. 运行方案：复制表达式和选择，不复制任何值。
        #    注意这里复制的是源 Project **当前**的运行方案，不是版本快照——
        #    RunConfiguration 挂在 Project 上，版本只固定文件内容。
        #    PUBLIC 读者 configurations 为空，整段跳过。
        for configuration in configurations:
            await self._repos.run_configurations.add(
                RunConfiguration(
                    id=ids.new_id(ids.RUN_CONFIGURATION),
                    project_id=project.id,
                    name=configuration.name,
                    working_directory=configuration.working_directory,
                    command=configuration.command,
                    environment_version_id=configuration.environment_version_id,
                    # EnvValue 里 Secret 项存的是引用表达式，不是值（GR-407）
                    environment_variables=dict(configuration.environment_variables),
                    input_bindings=configuration.input_bindings,
                    compute_plan_id=configuration.compute_plan_id,
                    compute_request=configuration.compute_request,
                    artifact_rules=configuration.artifact_rules,
                    description=configuration.description,
                )
            )

        # 5. 来源记录。名字抄一份：源被改名或删除之后这条仍然要读得通。
        await self._repos.fork_relations.add(
            ForkRelation(
                id=ids.new_id(ids.FORK_RELATION),
                project_id=project.id,
                source_project_id=source_version.project_id,
                source_version_id=source_version.id,
                source_owner=source_access.project.owner,
                source_project_name=source_access.project.name,
                source_version_label=source_version.label,
                created_by=user_id,
                created_at=now,
            )
        )

        await self._activity.record(
            actor_id=user_id,
            owner=owner,
            project_id=project.id,
            action=ActivityAction.PROJECT_FORKED,
            target_type=TargetType.PROJECT,
            target_id=project.id,
            target_name=project.name,
            detail=f"来自 {source_access.project.name} 的 {source_version.label}",
        )
        return project

    async def fork_source(self, user_id: str, project_id: str) -> ForkRelation | None:
        """这个 Project 是从哪儿来的。不是 Fork 出来的就返回 None。"""
        await self._guard.project(user_id, project_id, needs=Capability.PROJECT_VIEW)
        return await self._repos.fork_relations.get_for_project(project_id)

    async def _touch(self, project: Project) -> None:
        project.updated_at = self._clock.now()
        await self._repos.projects.update(project)


def _diff(left: dict[str, str], right: dict[str, str]) -> list[tuple[str, ChangeKind]]:
    """比较两组 ``路径 -> 内容摘要``，返回 ``(路径, 变化类型)``。"""
    changes: list[tuple[str, ChangeKind]] = []
    for path in sorted(set(left) | set(right)):
        if path not in left:
            changes.append((path, ChangeKind.ADDED))
        elif path not in right:
            changes.append((path, ChangeKind.REMOVED))
        elif left[path] != right[path]:
            changes.append((path, ChangeKind.MODIFIED))
    return changes


def _change_kind(previous_hash: str | None, current_hash: str | None) -> ChangeKind:
    if previous_hash is None:
        return ChangeKind.ADDED
    if current_hash is None:
        return ChangeKind.REMOVED
    return ChangeKind.MODIFIED
