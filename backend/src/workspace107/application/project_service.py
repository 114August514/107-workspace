"""Project、项目文件与版本用例。

Project Working State 可变，Project Version 不可变（GR-201）。
保存版本时对当前内容形成快照；恢复历史版本是把快照内容写回工作区，
不会改变那个历史版本本身。
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass

from ..domain import ids
from ..domain.capabilities import Capability
from ..domain.enums import ActivityAction, ChangeKind, InputSourceType, ProjectStatus, TargetType
from ..domain.errors import ConflictError, ObjectNotFound, ValidationFailed
from ..domain.models import (
    ForkRelation,
    Project,
    ProjectFile,
    ProjectVersion,
    ProjectVersionFile,
    RunConfiguration,
)
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

MAX_INLINE_PREVIEW_BYTES = 512 * 1024


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


@dataclass(frozen=True, slots=True)
class VersionDiffEntry:
    path: str
    change: ChangeKind


@dataclass(frozen=True, slots=True)
class WorkingTreeChange:
    path: str
    change: ChangeKind


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
    ) -> None:
        self._repos = repos
        self._guard = guard
        self._clock = clock
        self._storage = storage
        self._activity = activity
        # 上限从组合根注入而不是读全局配置：用例的依赖都写在构造函数上，
        # 测试要换一个小上限也不用改环境变量。
        self._max_file_bytes = max_file_bytes

    # -- Project --------------------------------------------------------

    async def list_for_workspace(
        self, user_id: str, workspace_id: str, page: PageRequest
    ) -> Page[Project]:
        await self._guard.legacy_workspace(user_id, workspace_id, needs=Capability.PROJECT_VIEW)
        return await self._repos.projects.list_for_workspace(workspace_id, page)

    async def list_recent_for_user(self, user_id: str, *, limit: int = 10) -> list[Project]:
        return await self._repos.projects.list_for_user(user_id, limit=limit)

    async def get(self, user_id: str, project_id: str) -> ProjectAccess:
        return await self._guard.project(user_id, project_id)

    async def create(
        self, user_id: str, workspace_id: str, name: str, description: str = ""
    ) -> Project:
        await self._guard.legacy_workspace(user_id, workspace_id, needs=Capability.PROJECT_CREATE)
        name = name.strip()
        if not name:
            raise ValidationFailed("Project 名称不能为空")
        if await self._repos.projects.name_exists(workspace_id, name):
            raise ConflictError(f"当前 Workspace 中已存在名为「{name}」的 Project")

        now = self._clock.now()
        project = Project(
            id=ids.new_id(ids.PROJECT),
            workspace_id=workspace_id,
            name=name,
            description=description,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        await self._repos.projects.add(project)
        await self._activity.record(
            actor_id=user_id,
            workspace_id=workspace_id,
            project_id=project.id,
            action=ActivityAction.PROJECT_CREATED,
            target_type=TargetType.PROJECT,
            target_id=project.id,
            target_name=project.name,
        )
        return project

    async def update(
        self,
        user_id: str,
        project_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        environment_version_id: str | None = None,
        inherit_workspace_environment: bool = False,
        default_run_configuration_id: str | None = None,
    ) -> Project:
        access = await self._guard.project(user_id, project_id, needs=Capability.PROJECT_UPDATE)
        project = access.project

        if name is not None:
            name = name.strip()
            if not name:
                raise ValidationFailed("Project 名称不能为空")
            if name != project.name and await self._repos.projects.name_exists(
                project.workspace_id, name
            ):
                raise ConflictError(f"当前 Workspace 中已存在名为「{name}」的 Project")
            project.name = name
        if description is not None:
            project.description = description
        if inherit_workspace_environment:
            project.environment_version_id = None
        elif environment_version_id is not None:
            version = await environment_version_for_owner_use(
                self._repos,
                user_id,
                environment_version_id,
                access.workspace.owner_reference,
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
            workspace_id=project.workspace_id,
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
        await self._guard.project(user_id, project_id)
        files = await self._repos.project_files.list_for_project(project_id)
        return sorted(files, key=lambda f: f.path)

    async def read_file(self, user_id: str, project_id: str, path: str) -> bytes:
        await self._guard.project(user_id, project_id)
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

        # 中间件按 Content-Length 挡掉的是明显超大的请求，
        # 但那个头可能缺失或被伪造，所以真正的上限在这里再判一次。
        if len(content) > self._max_file_bytes:
            limit_mb = self._max_file_bytes // (1024 * 1024)
            raise ValidationFailed(
                f"文件 {normalized} 超过单个文件上限 {limit_mb} MB。"
                "大数据集和模型权重应当作为共享资源管理，不要放进 Project 文件。"
            )

        content_hash = await self._storage.write_blob(content)

        record = ProjectFile(
            project_id=project_id,
            path=normalized,
            size=len(content),
            content_hash=content_hash,
            updated_at=self._clock.now(),
        )
        await self._repos.project_files.upsert(record)
        await self._touch(access.project)
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

        moved: list[ProjectFile] = []
        now = self._clock.now()
        for file in matched:
            suffix = file.path[len(src) :]
            new_path = dst + suffix
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
        await self._guard.project(user_id, project_id)
        latest = await self._repos.project_versions.latest(project_id)
        baseline = {f.path: f.content_hash for f in latest.files} if latest else {}
        current = {
            f.path: f.content_hash
            for f in await self._repos.project_files.list_for_project(project_id)
        }
        return [
            WorkingTreeChange(path=path, change=change) for path, change in _diff(baseline, current)
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
            workspace_id=access.project.workspace_id,
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
            workspace_id=access.project.workspace_id,
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
        target_workspace_id: str,
        *,
        name: str = "",
        description: str = "",
    ) -> Project:
        """从一个确定版本派生出新 Project。

        产生的是**新 Project**，不是源 Project 的分支（设计稿 §3.4.2）。
        新 Project 归目标 Workspace，从此和源 Project 没有任何持续关系（GR-502）。

        两侧都要校验：源版本可读、目标空间可写。少任何一边都是越权——
        只查源就等于「谁都能往别人空间里塞项目」，只查目标就等于
        「Fork 一下就能读到看不见的内容」。

        复制什么、不复制什么见 GR-503，下面按顺序标注了。
        **权益、凭据、成员权限、Run 历史一律不复制**——那些属于源 Workspace，
        跟着复制过来就是越权。

        Secret 只复制引用表达式，不复制值（GR-407）。值存在
        WorkspaceSecret 里，本来就不在复制路径上；目标空间没有同名 Secret 时
        提交前检查会拦下，这是**正确行为**，比静默降级好。
        """
        # 1. 源版本可读
        source_version = await self.get_version(user_id, version_id)
        source_access = await self._guard.project(
            user_id, source_version.project_id, needs=Capability.PROJECT_VIEW
        )

        # 2. 目标空间可写
        target = await self._guard.legacy_workspace(
            user_id, target_workspace_id, needs=Capability.PROJECT_CREATE
        )

        name = (name or source_access.project.name).strip()
        if not name:
            raise ValidationFailed("Project 名称不能为空")
        if await self._repos.projects.name_exists(target_workspace_id, name):
            raise ConflictError(f"当前 Workspace 中已存在名为「{name}」的 Project")

        target_owner = target.workspace.owner_reference
        project_environment_id = source_access.project.environment_version_id
        if (
            project_environment_id is not None
            and await environment_version_for_owner_use(
                self._repos, user_id, project_environment_id, target_owner
            )
            is None
        ):
            raise ObjectNotFound("Environment Version", project_environment_id)

        configurations = await self._repos.run_configurations.list_for_project(
            source_version.project_id
        )
        for configuration in configurations:
            configuration_environment_id = configuration.environment_version_id
            if (
                configuration_environment_id is not None
                and await environment_version_for_owner_use(
                    self._repos, user_id, configuration_environment_id, target_owner
                )
                is None
            ):
                raise ObjectNotFound("Environment Version", configuration_environment_id)
            for binding in configuration.input_bindings:
                if (
                    binding.source_type is InputSourceType.SHARED_RESOURCE_VERSION
                    and await shared_resource_version_for_owner_use(
                        self._repos, user_id, binding.source_id, target_owner
                    )
                    is None
                ):
                    raise ObjectNotFound("Shared Resource Version", binding.source_id)

        now = self._clock.now()
        project = Project(
            id=ids.new_id(ids.PROJECT),
            workspace_id=target_workspace_id,
            name=name,
            description=description or source_access.project.description,
            # Asset references were validated against the target owner before any writes.
            environment_version_id=source_access.project.environment_version_id,
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
                source_workspace_id=source_access.workspace.id,
                source_project_name=source_access.project.name,
                source_version_label=source_version.label,
                created_by=user_id,
                created_at=now,
            )
        )

        await self._activity.record(
            actor_id=user_id,
            workspace_id=target.workspace.id,
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
