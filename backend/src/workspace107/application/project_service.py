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
from ..domain.enums import ActivityAction, ChangeKind, ProjectStatus, TargetType
from ..domain.errors import (
    ConflictError,
    ObjectNotFound,
    ProjectContentIdentityMismatch,
    ProjectContentMissing,
    ValidationFailed,
)
from ..domain.models import (
    ForkRelation,
    Project,
    ProjectFile,
    ProjectVersion,
    ProjectVersionDetail,
    RunConfiguration,
)
from ..domain.pagination import Page, PageRequest
from ..domain.ports.clock import Clock
from ..domain.ports.project_content import CommitManifest, ProjectContentPort
from ..domain.ports.repositories import Repositories
from .access import AccessGuard, ProjectAccess
from .activity import ActivityRecorder

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
        content: ProjectContentPort,
        activity: ActivityRecorder,
        *,
        max_file_bytes: int,
    ) -> None:
        self._repos = repos
        self._guard = guard
        self._clock = clock
        self._content = content
        self._activity = activity
        # 上限从组合根注入而不是读全局配置：用例的依赖都写在构造函数上，
        # 测试要换一个小上限也不用改环境变量。
        self._max_file_bytes = max_file_bytes

    # -- Project --------------------------------------------------------

    async def list_for_workspace(
        self, user_id: str, workspace_id: str, page: PageRequest
    ) -> Page[Project]:
        await self._guard.workspace(user_id, workspace_id, needs=Capability.PROJECT_VIEW)
        return await self._repos.projects.list_for_workspace(workspace_id, page)

    async def list_recent_for_user(self, user_id: str, *, limit: int = 10) -> list[Project]:
        return await self._repos.projects.list_for_user(user_id, limit=limit)

    async def get(self, user_id: str, project_id: str) -> ProjectAccess:
        return await self._guard.project(user_id, project_id)

    async def create(
        self, user_id: str, workspace_id: str, name: str, description: str = ""
    ) -> Project:
        await self._guard.workspace(user_id, workspace_id, needs=Capability.PROJECT_CREATE)
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
            repository_identity=ids.new_id(ids.PROJECT_REPOSITORY),
            description=description,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        await self._content.initialize_project(project.id, project.repository_identity)
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
            version = await self._repos.environments.get_version(environment_version_id)
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
        access = await self._guard.project(user_id, project_id)
        return await self._content.list_working_files(
            project_id, access.project.repository_identity
        )

    async def read_file(self, user_id: str, project_id: str, path: str) -> bytes:
        access = await self._guard.project(user_id, project_id)
        return await self._content.read_working_file(
            project_id, access.project.repository_identity, normalize_path(path)
        )

    async def write_file(
        self, user_id: str, project_id: str, path: str, content: bytes
    ) -> ProjectFile:
        access = await self._guard.project(
            user_id, project_id, needs=Capability.PROJECT_CONTENT_WRITE
        )
        normalized = normalize_path(path)
        if len(content) > self._max_file_bytes:
            limit_mb = self._max_file_bytes // (1024 * 1024)
            raise ValidationFailed(
                f"文件 {normalized} 超过单个文件上限 {limit_mb} MB。"
                "大数据集和模型权重应当作为共享资源管理，不要放进 Project 文件。"
            )

        record = await self._content.write_working_file(
            project_id,
            access.project.repository_identity,
            normalized,
            content,
            self._clock.now(),
        )
        await self._touch(access.project)
        return record

    async def delete_path(self, user_id: str, project_id: str, path: str) -> int:
        access = await self._guard.project(
            user_id, project_id, needs=Capability.PROJECT_CONTENT_WRITE
        )
        removed = await self._content.delete_working_path(
            project_id, access.project.repository_identity, normalize_path(path)
        )
        await self._touch(access.project)
        return removed

    async def move_path(
        self, user_id: str, project_id: str, source: str, destination: str
    ) -> list[ProjectFile]:
        access = await self._guard.project(
            user_id, project_id, needs=Capability.PROJECT_CONTENT_WRITE
        )
        src = normalize_path(source)
        dst = normalize_path(destination)
        if src == dst:
            raise ValidationFailed("源路径和目标路径相同")
        if dst.startswith(src + "/"):
            raise ValidationFailed("不能把目录移动到自己的子目录中")
        moved = await self._content.move_working_path(
            project_id,
            access.project.repository_identity,
            src,
            dst,
            self._clock.now(),
        )
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

    async def get_version_detail(self, user_id: str, version_id: str) -> ProjectVersionDetail:
        version = await self.get_version(user_id, version_id)
        manifest = await self._verified_manifest(version)
        return ProjectVersionDetail(version=version, files=manifest.files)

    async def working_changes(self, user_id: str, project_id: str) -> list[WorkingTreeChange]:
        """查看当前 Working State 与最近保存 commit 的差异。"""
        access = await self._guard.project(user_id, project_id)
        latest = await self._repos.project_versions.latest(project_id)
        changes = await self._content.working_changes(
            project_id,
            access.project.repository_identity,
            latest.commit_oid if latest is not None else None,
        )
        return [WorkingTreeChange(path=path, change=change) for path, change in changes]

    async def save_version(self, user_id: str, project_id: str, message: str) -> ProjectVersion:
        access = await self._guard.project(
            user_id, project_id, needs=Capability.PROJECT_CONTENT_WRITE
        )
        latest = await self._repos.project_versions.latest(project_id)
        created_at = self._clock.now()
        resolved_message = message.strip() or "保存版本"
        version_id = ids.new_id(ids.PROJECT_VERSION)
        manifest = await self._content.commit_working(
            project_id,
            access.project.repository_identity,
            version_id=version_id,
            parent_commit_oid=latest.commit_oid if latest is not None else None,
            message=resolved_message,
            created_by=user_id,
            created_at=created_at,
        )
        version = ProjectVersion(
            id=version_id,
            project_id=project_id,
            sequence=await self._repos.project_versions.next_sequence(project_id),
            message=resolved_message,
            commit_oid=manifest.commit_oid,
            file_count=manifest.file_count,
            total_size=manifest.total_size,
            created_by=user_id,
            created_at=created_at,
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
        project = await self._repos.projects.get(base.project_id)
        if project is None:
            raise ObjectNotFound("Project", base.project_id)
        changes = await self._content.diff_commits(
            base.project_id,
            project.repository_identity,
            base.commit_oid,
            target.commit_oid,
        )
        return [VersionDiffEntry(path=path, change=change) for path, change in changes]

    async def restore_version(self, user_id: str, version_id: str) -> list[ProjectFile]:
        version = await self.get_version(user_id, version_id)
        access = await self._guard.project(
            user_id, version.project_id, needs=Capability.PROJECT_CONTENT_WRITE
        )
        restored = await self._content.restore_working(
            version.project_id,
            access.project.repository_identity,
            version.commit_oid,
            self._clock.now(),
        )
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
        project = await self._repos.projects.get(version.project_id)
        if project is None:
            raise ObjectNotFound("Project Version", version_id)
        return await self._content.read_commit_file(
            version.project_id,
            project.repository_identity,
            version.commit_oid,
            normalize_path(path),
        )

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
        target = await self._guard.workspace(
            user_id, target_workspace_id, needs=Capability.PROJECT_CREATE
        )

        name = (name or source_access.project.name).strip()
        if not name:
            raise ValidationFailed("Project 名称不能为空")
        if await self._repos.projects.name_exists(target_workspace_id, name):
            raise ConflictError(f"当前 Workspace 中已存在名为「{name}」的 Project")

        now = self._clock.now()
        project = Project(
            id=ids.new_id(ids.PROJECT),
            workspace_id=target_workspace_id,
            name=name,
            repository_identity=ids.new_id(ids.PROJECT_REPOSITORY),
            description=description or source_access.project.description,
            # 环境选择作为可复用引用跟着复制（GR-503）。目标空间不一定能用，
            # 创建 Run 时仍需按目标 Workspace 的资格重新校验（GR-401）。
            environment_version_id=source_access.project.environment_version_id,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        fork_message = f"Fork 自 {source_access.project.name} 的 {source_version.label}"
        version_id = ids.new_id(ids.PROJECT_VERSION)
        manifest = await self._content.fork_commit(
            source_version.project_id,
            source_access.project.repository_identity,
            source_version.commit_oid,
            project.id,
            project.repository_identity,
            version_id=version_id,
            message=fork_message,
            created_by=user_id,
            created_at=now,
        )
        await self._repos.projects.add(project)
        await self._repos.project_versions.add(
            ProjectVersion(
                id=version_id,
                project_id=project.id,
                sequence=1,
                message=fork_message,
                commit_oid=manifest.commit_oid,
                file_count=manifest.file_count,
                total_size=manifest.total_size,
                created_by=user_id,
                created_at=now,
            )
        )

        # 4. 运行方案：复制表达式和选择，不复制任何值。
        #    注意这里复制的是源 Project **当前**的运行方案，不是版本快照——
        #    RunConfiguration 挂在 Project 上，版本只固定文件内容。
        for configuration in await self._repos.run_configurations.list_for_project(
            source_version.project_id
        ):
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

    async def _verified_manifest(self, version: ProjectVersion) -> CommitManifest:
        project = await self._repos.projects.get(version.project_id)
        if project is None:
            raise ProjectContentMissing(f"Project {version.project_id} 不存在")
        manifest = await self._content.manifest(
            version.project_id, project.repository_identity, version.commit_oid
        )
        if manifest.file_count != version.file_count or manifest.total_size != version.total_size:
            raise ProjectContentIdentityMismatch(
                f"Project Version {version.id} 的 Git manifest 与持久化 identity 不一致"
            )
        return manifest

    async def _touch(self, project: Project) -> None:
        project.updated_at = self._clock.now()
        await self._repos.projects.update(project)
