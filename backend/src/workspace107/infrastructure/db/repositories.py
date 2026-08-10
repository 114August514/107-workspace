"""基于 SQLAlchemy 的仓储实现。

行对象与领域对象在这里互相转换。application 层拿到的永远是领域对象，
不会看到 ``*Row``。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.compute import ComputePlan, ComputeRequest, ResourceEntitlement, SchedulerMapping
from ...domain.enums import (
    ActivityAction,
    ArtifactStatus,
    InputSourceType,
    MembershipStatus,
    NotificationType,
    ProjectStatus,
    RunEventType,
    RunStatus,
    TargetType,
    WorkspaceKind,
    WorkspaceRole,
)
from ...domain.errors import ConflictError
from ...domain.execution import ExecutionIntent
from ...domain.models import (
    Activity,
    Artifact,
    ArtifactCollectionRule,
    Environment,
    EnvironmentVersion,
    ForkRelation,
    IdempotencyRecord,
    InputBinding,
    Membership,
    Notification,
    Project,
    ProjectFile,
    ProjectVersion,
    ProjectVersionFile,
    Run,
    RunConfiguration,
    RunEvent,
    User,
    Workspace,
    WorkspaceVariable,
)
from ...domain.pagination import Page, PageRequest
from ...domain.run_snapshot import RunSnapshot
from ...domain.secrets import parse_env_value
from . import tables as t

# 唯一约束冲突 -> 领域冲突错误。
#
# 「先查重、再插入」在并发下必然有窗口，唯一约束是最后一道防线。
# 但它抛的是 SQLAlchemy 异常，不翻译的话用户看到的是 500 而不是 409，
# 排查时也看不出到底撞了哪条约束。
#
# 每条规则给两个匹配词：PostgreSQL 的报错带约束名，SQLite 的只带表名和列名。
_CONFLICT_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("uq_version_sequence", "project_versions.sequence"),
        "有其他人同时保存了这个 Project 的版本，请刷新后重试",
    ),
    (("users.username",), "这个用户名已经被占用"),
    (("uq_personal_workspace",), "这个用户已经有 Personal Workspace 了"),
    (("uq_project_name", "projects.name"), "当前 Workspace 中已存在同名 Project"),
    (("uq_membership", "memberships.user_id"), "该用户已经是成员或已被邀请"),
    (
        ("uq_entitlement", "resource_entitlements.compute_plan_id"),
        "该 Workspace 已经拥有这个算力方案的资源权益",
    ),
    (
        ("idempotency_keys_pkey", "idempotency_keys.key"),
        "相同的提交请求正在处理中，请稍后查看 Run 列表，不要重复提交",
    ),
)


async def _flush(session: AsyncSession) -> None:
    """提交待写入内容，并把唯一约束冲突翻译成 :class:`ConflictError`。"""
    try:
        await session.flush()
    except IntegrityError as exc:
        detail = str(exc.orig)
        for tokens, message in _CONFLICT_RULES:
            if any(token in detail for token in tokens):
                raise ConflictError(message) from exc
        raise


async def _paginate[TRow, TModel](
    session: AsyncSession,
    stmt: Any,
    page: PageRequest,
    convert: Any,
) -> Page[TModel]:
    """执行一次分页查询：先数总量，再取当前页。

    两次查询而不是一次窗口函数——可读性更重要，而且这两条都走同一个索引。
    """
    total = (
        await session.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    ).scalar_one()
    rows = (await session.execute(stmt.offset(page.offset).limit(page.page_size))).scalars().all()
    return Page(
        items=[convert(row) for row in rows],
        page=page.page,
        page_size=page.page_size,
        total=int(total),
    )


def _aware(value: datetime | None) -> datetime | None:
    """SQLite 读回来的时间没有时区，这里统一补成 UTC。"""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _required(value: datetime | None) -> datetime:
    result = _aware(value)
    assert result is not None
    return result


class UserRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        self._session.add(
            t.UserRow(
                id=user.id,
                username=user.username,
                display_name=user.display_name,
                email=user.email,
                created_at=user.created_at or datetime.now(UTC),
            )
        )
        await _flush(self._session)

    async def get(self, user_id: str) -> User | None:
        row = await self._session.get(t.UserRow, user_id)
        return _to_user(row) if row else None

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(t.UserRow).where(t.UserRow.username == username)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_user(row) if row else None


class WorkspaceRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, workspace: Workspace) -> None:
        self._session.add(
            t.WorkspaceRow(
                id=workspace.id,
                kind=workspace.kind.value,
                name=workspace.name,
                description=workspace.description,
                owner_id=workspace.owner_id,
                default_environment_version_id=workspace.default_environment_version_id,
                created_at=workspace.created_at or datetime.now(UTC),
            )
        )
        await _flush(self._session)

    async def get(self, workspace_id: str) -> Workspace | None:
        row = await self._session.get(t.WorkspaceRow, workspace_id)
        return _to_workspace(row) if row else None

    async def update(self, workspace: Workspace) -> None:
        row = await self._session.get(t.WorkspaceRow, workspace.id)
        if row is None:
            return
        row.name = workspace.name
        row.description = workspace.description
        row.owner_id = workspace.owner_id
        row.default_environment_version_id = workspace.default_environment_version_id
        await _flush(self._session)

    async def get_personal(self, owner_id: str) -> Workspace | None:
        stmt = select(t.WorkspaceRow).where(
            t.WorkspaceRow.owner_id == owner_id,
            t.WorkspaceRow.kind == WorkspaceKind.PERSONAL.value,
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return _to_workspace(row) if row else None

    async def list_for_user(self, user_id: str) -> list[Workspace]:
        member_ids = select(t.MembershipRow.workspace_id).where(
            t.MembershipRow.user_id == user_id,
            t.MembershipRow.status == MembershipStatus.ACTIVE.value,
        )
        stmt = (
            select(t.WorkspaceRow)
            .where(
                (t.WorkspaceRow.owner_id == user_id) | t.WorkspaceRow.id.in_(member_ids),
            )
            .order_by(t.WorkspaceRow.kind, t.WorkspaceRow.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_workspace(row) for row in rows]


class MembershipRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, membership: Membership) -> None:
        self._session.add(
            t.MembershipRow(
                id=membership.id,
                workspace_id=membership.workspace_id,
                user_id=membership.user_id,
                role=membership.role.value,
                status=membership.status.value,
                created_at=membership.created_at or datetime.now(UTC),
            )
        )
        await _flush(self._session)

    async def update(self, membership: Membership) -> None:
        row = await self._session.get(t.MembershipRow, membership.id)
        if row is None:
            return
        row.role = membership.role.value
        row.status = membership.status.value
        await _flush(self._session)

    async def get(self, workspace_id: str, user_id: str) -> Membership | None:
        stmt = select(t.MembershipRow).where(
            t.MembershipRow.workspace_id == workspace_id,
            t.MembershipRow.user_id == user_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_membership(row) if row else None

    async def list_pending_for_user(self, user_id: str) -> list[Membership]:
        stmt = (
            select(t.MembershipRow)
            .where(
                t.MembershipRow.user_id == user_id,
                t.MembershipRow.status == MembershipStatus.INVITED.value,
            )
            .order_by(t.MembershipRow.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_membership(row) for row in rows]

    async def list_for_workspace(self, workspace_id: str) -> list[Membership]:
        stmt = (
            select(t.MembershipRow)
            .where(
                t.MembershipRow.workspace_id == workspace_id,
                t.MembershipRow.status.in_(
                    [MembershipStatus.ACTIVE.value, MembershipStatus.INVITED.value]
                ),
            )
            .order_by(t.MembershipRow.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_membership(row) for row in rows]


class VariableRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_workspace(self, workspace_id: str) -> list[WorkspaceVariable]:
        stmt = (
            select(t.WorkspaceVariableRow)
            .where(t.WorkspaceVariableRow.workspace_id == workspace_id)
            .order_by(t.WorkspaceVariableRow.name)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            WorkspaceVariable(workspace_id=r.workspace_id, name=r.name, value=r.value) for r in rows
        ]

    async def upsert(self, variable: WorkspaceVariable) -> None:
        row = await self._session.get(
            t.WorkspaceVariableRow, (variable.workspace_id, variable.name)
        )
        if row is None:
            self._session.add(
                t.WorkspaceVariableRow(
                    workspace_id=variable.workspace_id,
                    name=variable.name,
                    value=variable.value,
                )
            )
        else:
            row.value = variable.value
        await _flush(self._session)

    async def delete(self, workspace_id: str, name: str) -> None:
        await self._session.execute(
            delete(t.WorkspaceVariableRow).where(
                t.WorkspaceVariableRow.workspace_id == workspace_id,
                t.WorkspaceVariableRow.name == name,
            )
        )
        await _flush(self._session)


class ProjectRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, project: Project) -> None:
        self._session.add(
            t.ProjectRow(
                id=project.id,
                workspace_id=project.workspace_id,
                name=project.name,
                description=project.description,
                status=project.status.value,
                environment_version_id=project.environment_version_id,
                default_run_configuration_id=project.default_run_configuration_id,
                created_by=project.created_by,
                created_at=project.created_at or datetime.now(UTC),
                updated_at=project.updated_at or datetime.now(UTC),
            )
        )
        await _flush(self._session)

    async def get(self, project_id: str) -> Project | None:
        row = await self._session.get(t.ProjectRow, project_id)
        return _to_project(row) if row else None

    async def update(self, project: Project) -> None:
        row = await self._session.get(t.ProjectRow, project.id)
        if row is None:
            return
        row.name = project.name
        row.description = project.description
        row.status = project.status.value
        row.environment_version_id = project.environment_version_id
        row.default_run_configuration_id = project.default_run_configuration_id
        row.updated_at = project.updated_at or datetime.now(UTC)
        await _flush(self._session)

    async def list_for_workspace(self, workspace_id: str, page: PageRequest) -> Page[Project]:
        stmt = (
            select(t.ProjectRow)
            .where(t.ProjectRow.workspace_id == workspace_id)
            .order_by(t.ProjectRow.updated_at.desc())
        )
        return await _paginate(self._session, stmt, page, _to_project)

    async def list_for_user(self, user_id: str, *, limit: int) -> list[Project]:
        visible = _visible_workspace_ids(user_id)
        stmt = (
            select(t.ProjectRow)
            .where(t.ProjectRow.workspace_id.in_(visible))
            .order_by(t.ProjectRow.updated_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_project(row) for row in rows]

    async def name_exists(self, workspace_id: str, name: str) -> bool:
        stmt = (
            select(func.count())
            .select_from(t.ProjectRow)
            .where(t.ProjectRow.workspace_id == workspace_id, t.ProjectRow.name == name)
        )
        return bool((await self._session.execute(stmt)).scalar_one())


class ProjectFileRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_project(self, project_id: str) -> list[ProjectFile]:
        stmt = (
            select(t.ProjectFileRow)
            .where(t.ProjectFileRow.project_id == project_id)
            .order_by(t.ProjectFileRow.path)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_project_file(row) for row in rows]

    async def get(self, project_id: str, path: str) -> ProjectFile | None:
        row = await self._session.get(t.ProjectFileRow, (project_id, path))
        return _to_project_file(row) if row else None

    async def upsert(self, file: ProjectFile) -> None:
        row = await self._session.get(t.ProjectFileRow, (file.project_id, file.path))
        if row is None:
            self._session.add(
                t.ProjectFileRow(
                    project_id=file.project_id,
                    path=file.path,
                    size=file.size,
                    content_hash=file.content_hash,
                    updated_at=file.updated_at or datetime.now(UTC),
                )
            )
        else:
            row.size = file.size
            row.content_hash = file.content_hash
            row.updated_at = file.updated_at or datetime.now(UTC)
        await _flush(self._session)

    async def delete(self, project_id: str, path: str) -> None:
        await self._session.execute(
            delete(t.ProjectFileRow).where(
                t.ProjectFileRow.project_id == project_id, t.ProjectFileRow.path == path
            )
        )
        await _flush(self._session)

    async def delete_under(self, project_id: str, prefix: str) -> int:
        result = await self._session.execute(
            delete(t.ProjectFileRow).where(
                t.ProjectFileRow.project_id == project_id,
                # autoescape 不能省：startswith 生成的是 LIKE，
                # 而 % 和 _ 在路径里是合法字符。删一个叫 "%" 的目录会变成
                # LIKE '%/%'，把项目里所有子目录的文件一起删掉。
                t.ProjectFileRow.path.startswith(prefix, autoescape=True),
            )
        )
        await _flush(self._session)
        return int(result.rowcount or 0)


class ProjectVersionRepositoryImpl:
    """不可变对象仓储：只有 add 和读取。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, version: ProjectVersion) -> None:
        self._session.add(
            t.ProjectVersionRow(
                id=version.id,
                project_id=version.project_id,
                sequence=version.sequence,
                message=version.message,
                created_by=version.created_by,
                created_at=version.created_at,
            )
        )
        # 先把版本行落库，再插文件行。
        #
        # 这两张表之间只有外键，没有 ORM relationship，所以 SQLAlchemy 的工作单元
        # 不知道它们的先后依赖，同一次 flush 里可能先插子行。SQLite 默认不校验外键，
        # 这个顺序问题在本地测试里看不出来，到 PostgreSQL 上就是 ForeignKeyViolation。
        await _flush(self._session)

        for entry in version.files:
            self._session.add(
                t.ProjectVersionFileRow(
                    version_id=version.id,
                    path=entry.path,
                    size=entry.size,
                    content_hash=entry.content_hash,
                )
            )
        await _flush(self._session)

    async def get(self, version_id: str) -> ProjectVersion | None:
        row = await self._session.get(t.ProjectVersionRow, version_id)
        if row is None:
            return None
        return await self._hydrate(row)

    async def list_for_project(self, project_id: str, page: PageRequest) -> Page[ProjectVersion]:
        stmt = (
            select(t.ProjectVersionRow)
            .where(t.ProjectVersionRow.project_id == project_id)
            .order_by(t.ProjectVersionRow.sequence.desc())
        )
        total = (
            await self._session.execute(
                select(func.count()).select_from(stmt.order_by(None).subquery())
            )
        ).scalar_one()
        rows = (
            (await self._session.execute(stmt.offset(page.offset).limit(page.page_size)))
            .scalars()
            .all()
        )
        return Page(
            items=[await self._hydrate(row) for row in rows],
            page=page.page,
            page_size=page.page_size,
            total=int(total),
        )

    async def latest(self, project_id: str) -> ProjectVersion | None:
        stmt = (
            select(t.ProjectVersionRow)
            .where(t.ProjectVersionRow.project_id == project_id)
            .order_by(t.ProjectVersionRow.sequence.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return await self._hydrate(row) if row else None

    async def next_sequence(self, project_id: str) -> int:
        stmt = select(func.max(t.ProjectVersionRow.sequence)).where(
            t.ProjectVersionRow.project_id == project_id
        )
        current = (await self._session.execute(stmt)).scalar_one_or_none()
        return int(current or 0) + 1

    async def _hydrate(self, row: t.ProjectVersionRow) -> ProjectVersion:
        stmt = (
            select(t.ProjectVersionFileRow)
            .where(t.ProjectVersionFileRow.version_id == row.id)
            .order_by(t.ProjectVersionFileRow.path)
        )
        files = (await self._session.execute(stmt)).scalars().all()
        return ProjectVersion(
            id=row.id,
            project_id=row.project_id,
            sequence=row.sequence,
            message=row.message,
            files=tuple(
                ProjectVersionFile(path=f.path, size=f.size, content_hash=f.content_hash)
                for f in files
            ),
            created_by=row.created_by,
            created_at=_required(row.created_at),
        )


class EnvironmentRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_environments(self) -> list[Environment]:
        stmt = select(t.EnvironmentRow).order_by(t.EnvironmentRow.name)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            Environment(
                id=r.id,
                name=r.name,
                description=r.description,
                owner_workspace_id=r.owner_workspace_id,
            )
            for r in rows
        ]

    async def get_environment(self, environment_id: str) -> Environment | None:
        row = await self._session.get(t.EnvironmentRow, environment_id)
        if row is None:
            return None
        return Environment(
            id=row.id,
            name=row.name,
            description=row.description,
            owner_workspace_id=row.owner_workspace_id,
        )

    async def list_versions(self, environment_id: str) -> list[EnvironmentVersion]:
        stmt = (
            select(t.EnvironmentVersionRow)
            .where(t.EnvironmentVersionRow.environment_id == environment_id)
            .order_by(t.EnvironmentVersionRow.version)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_environment_version(r) for r in rows]

    async def get_version(self, version_id: str) -> EnvironmentVersion | None:
        row = await self._session.get(t.EnvironmentVersionRow, version_id)
        return _to_environment_version(row) if row else None


class ComputePlanRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[ComputePlan]:
        stmt = select(t.ComputePlanRow).order_by(t.ComputePlanRow.code)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_compute_plan(r) for r in rows]

    async def get(self, plan_id: str) -> ComputePlan | None:
        row = await self._session.get(t.ComputePlanRow, plan_id)
        return _to_compute_plan(row) if row else None


class EntitlementRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_workspace(self, workspace_id: str) -> list[ResourceEntitlement]:
        stmt = select(t.ResourceEntitlementRow).where(
            t.ResourceEntitlementRow.workspace_id == workspace_id
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entitlement(r) for r in rows]

    async def get_for_plan(
        self, workspace_id: str, compute_plan_id: str
    ) -> ResourceEntitlement | None:
        stmt = select(t.ResourceEntitlementRow).where(
            t.ResourceEntitlementRow.workspace_id == workspace_id,
            t.ResourceEntitlementRow.compute_plan_id == compute_plan_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entitlement(row) if row else None

    async def add(self, entitlement: ResourceEntitlement) -> None:
        self._session.add(
            t.ResourceEntitlementRow(
                id=entitlement.id,
                workspace_id=entitlement.workspace_id,
                compute_plan_id=entitlement.compute_plan_id,
                max_concurrent_runs=entitlement.max_concurrent_runs,
                expires_at=entitlement.expires_at,
            )
        )
        await _flush(self._session)

    async def lock_for_plan(
        self, workspace_id: str, compute_plan_id: str
    ) -> ResourceEntitlement | None:
        """SELECT ... FOR UPDATE，锁到事务结束。

        PostgreSQL 上这行会被真正独占，第二个并发请求阻塞到第一个提交为止。
        SQLite 不支持 FOR UPDATE，SQLAlchemy 的方言会忽略它——开发和测试环境
        依赖 SQLite 自身的写串行化，生产环境（PostgreSQL）才有严格保证。
        """
        stmt = (
            select(t.ResourceEntitlementRow)
            .where(
                t.ResourceEntitlementRow.workspace_id == workspace_id,
                t.ResourceEntitlementRow.compute_plan_id == compute_plan_id,
            )
            .with_for_update()
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entitlement(row) if row else None


class RunConfigurationRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, configuration: RunConfiguration) -> None:
        self._session.add(
            t.RunConfigurationRow(
                id=configuration.id,
                project_id=configuration.project_id,
                name=configuration.name,
                description=configuration.description,
                working_directory=configuration.working_directory,
                command=configuration.command,
                environment_version_id=configuration.environment_version_id,
                environment_variables=_env_to_payload(configuration),
                input_bindings=[b.as_payload() for b in configuration.input_bindings],
                compute_plan_id=configuration.compute_plan_id,
                compute_request=(
                    configuration.compute_request.as_payload()
                    if isinstance(configuration.compute_request, ComputeRequest)
                    else None
                ),
                artifact_rules=[r.as_payload() for r in configuration.artifact_rules],
            )
        )
        await _flush(self._session)

    async def get(self, configuration_id: str) -> RunConfiguration | None:
        row = await self._session.get(t.RunConfigurationRow, configuration_id)
        return _to_run_configuration(row) if row else None

    async def update(self, configuration: RunConfiguration) -> None:
        row = await self._session.get(t.RunConfigurationRow, configuration.id)
        if row is None:
            return
        row.name = configuration.name
        row.description = configuration.description
        row.working_directory = configuration.working_directory
        row.command = configuration.command
        row.environment_version_id = configuration.environment_version_id
        row.environment_variables = _env_to_payload(configuration)
        row.input_bindings = [b.as_payload() for b in configuration.input_bindings]
        row.compute_plan_id = configuration.compute_plan_id
        row.compute_request = (
            configuration.compute_request.as_payload()
            if isinstance(configuration.compute_request, ComputeRequest)
            else None
        )
        row.artifact_rules = [r.as_payload() for r in configuration.artifact_rules]
        await _flush(self._session)

    async def delete(self, configuration_id: str) -> None:
        await self._session.execute(
            delete(t.RunConfigurationRow).where(t.RunConfigurationRow.id == configuration_id)
        )
        await _flush(self._session)

    async def list_for_project(self, project_id: str) -> list[RunConfiguration]:
        stmt = (
            select(t.RunConfigurationRow)
            .where(t.RunConfigurationRow.project_id == project_id)
            .order_by(t.RunConfigurationRow.name)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_run_configuration(r) for r in rows]


class RunSnapshotRepositoryImpl:
    """不可变对象仓储：只有 add 和 get，刻意没有 update（GR-202）。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, snapshot: RunSnapshot) -> None:
        self._session.add(t.RunSnapshotRow(id=snapshot.id, payload=snapshot.to_payload()))
        await _flush(self._session)

    async def get(self, snapshot_id: str) -> RunSnapshot | None:
        row = await self._session.get(t.RunSnapshotRow, snapshot_id)
        if row is None:
            return None
        return RunSnapshot.from_payload(row.id, dict(row.payload))


class RunRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, run: Run) -> None:
        self._session.add(
            t.RunRow(
                id=run.id,
                project_id=run.project_id,
                workspace_id=run.workspace_id,
                snapshot_id=run.snapshot_id,
                compute_plan_id=run.compute_plan_id,
                source_run_configuration_id=run.source_run_configuration_id,
                source_run_id=run.source_run_id,
                name=run.name,
                status=run.status.value,
                scheduler_job_id=run.scheduler_job_id,
                exit_code=run.exit_code,
                failure_reason=run.failure_reason,
                created_by=run.created_by,
                created_at=run.created_at or datetime.now(UTC),
                submitted_at=run.submitted_at,
                started_at=run.started_at,
                finished_at=run.finished_at,
            )
        )
        await _flush(self._session)

    async def get(self, run_id: str) -> Run | None:
        row = await self._session.get(t.RunRow, run_id)
        return _to_run(row) if row else None

    async def update(self, run: Run) -> None:
        row = await self._session.get(t.RunRow, run.id)
        if row is None:
            return
        row.name = run.name
        row.status = run.status.value
        row.scheduler_job_id = run.scheduler_job_id
        row.exit_code = run.exit_code
        row.failure_reason = run.failure_reason
        row.submitted_at = run.submitted_at
        row.started_at = run.started_at
        row.finished_at = run.finished_at
        await _flush(self._session)

    async def list_for_project(self, project_id: str, page: PageRequest) -> Page[Run]:
        stmt = (
            select(t.RunRow)
            .where(t.RunRow.project_id == project_id)
            .order_by(t.RunRow.created_at.desc())
        )
        return await _paginate(self._session, stmt, page, _to_run)

    async def list_for_user(self, user_id: str, *, limit: int) -> list[Run]:
        visible = _visible_workspace_ids(user_id)
        stmt = (
            select(t.RunRow)
            .where(t.RunRow.workspace_id.in_(visible))
            .order_by(t.RunRow.created_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_run(row) for row in rows]

    async def count_unfinished_for_plan(self, workspace_id: str, compute_plan_id: str) -> int:
        """数「这个 Workspace 在这个算力方案上」还有几个未结束的 Run。

        必须带 compute_plan_id：当前实现按「Workspace × 方案」授予并发额度，
        锁的也是那一条权益行。**计数范围大于加锁范围就等于没锁**——
        两个请求提交到不同方案时锁的是不同的行，谁都不阻塞谁，
        却都读到同一个更大范围的计数，双双通过。
        """
        stmt = (
            select(func.count())
            .select_from(t.RunRow)
            .where(
                t.RunRow.workspace_id == workspace_id,
                t.RunRow.compute_plan_id == compute_plan_id,
                t.RunRow.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value]),
            )
        )
        return int((await self._session.execute(stmt)).scalar_one())


class ExecutionIntentRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, intent: ExecutionIntent) -> None:
        self._session.add(
            t.RunExecutionIntentRow(
                run_id=intent.run_id,
                phase=intent.phase.value,
                correlation=intent.correlation,
                attempt_no=intent.attempt_no,
                next_attempt_at=func.now(),
                cancel_requested_at=intent.cancel_requested_at,
                lease_owner=intent.lease_owner,
                lease_token=intent.lease_token,
                lease_generation=intent.lease_generation,
                lease_expires_at=intent.lease_expires_at,
                uncertainty_code=intent.uncertainty_code,
                uncertainty_detail=intent.uncertainty_detail,
                observed_scheduler_state=intent.observed_scheduler_state,
                observed_exit_code=intent.observed_exit_code,
                observed_started_at=intent.observed_started_at,
                observed_finished_at=intent.observed_finished_at,
                observed_reason=intent.observed_reason,
                created_at=func.now(),
                updated_at=func.now(),
                completed_at=intent.completed_at,
            )
        )
        await _flush(self._session)

    async def request_cancel(self, run_id: str, at: datetime) -> bool:
        result = await self._session.execute(
            update(t.RunExecutionIntentRow)
            .where(
                t.RunExecutionIntentRow.run_id == run_id,
                t.RunExecutionIntentRow.completed_at.is_(None),
            )
            .values(cancel_requested_at=at, next_attempt_at=func.now(), updated_at=func.now())
        )
        return int(result.rowcount or 0) == 1


class IdempotencyRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find(self, workspace_id: str, key: str) -> IdempotencyRecord | None:
        row = await self._session.get(t.IdempotencyKeyRow, (workspace_id, key))
        if row is None:
            return None
        return IdempotencyRecord(
            workspace_id=row.workspace_id,
            key=row.key,
            endpoint=row.endpoint,
            run_id=row.run_id,
            created_at=_required(row.created_at),
        )

    async def reserve(self, workspace_id: str, key: str, endpoint: str) -> None:
        """登记这个 key 并立刻落库。

        立刻 flush 是关键：复合主键的冲突要在这一刻就暴露出来，
        而不是等到请求末尾——那时候作业已经提交给调度系统了。
        """
        self._session.add(
            t.IdempotencyKeyRow(
                workspace_id=workspace_id,
                key=key,
                endpoint=endpoint,
                run_id=None,
                created_at=datetime.now(UTC),
            )
        )
        await _flush(self._session)

    async def attach_run(self, workspace_id: str, key: str, run_id: str) -> None:
        row = await self._session.get(t.IdempotencyKeyRow, (workspace_id, key))
        if row is None:  # pragma: no cover - reserve 一定先于它调用
            return
        row.run_id = run_id
        await _flush(self._session)


class RunEventRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: RunEvent) -> None:
        self._session.add(
            t.RunEventRow(
                id=event.id,
                run_id=event.run_id,
                type=event.type.value,
                message=event.message,
                created_at=event.created_at,
            )
        )
        await _flush(self._session)

    async def list_for_run(self, run_id: str) -> list[RunEvent]:
        stmt = (
            select(t.RunEventRow)
            .where(t.RunEventRow.run_id == run_id)
            .order_by(t.RunEventRow.created_at, t.RunEventRow.id)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            RunEvent(
                id=r.id,
                run_id=r.run_id,
                type=RunEventType(r.type),
                message=r.message,
                created_at=_required(r.created_at),
            )
            for r in rows
        ]


class ArtifactRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, artifact: Artifact) -> None:
        self._session.add(
            t.ArtifactRow(
                id=artifact.id,
                run_id=artifact.run_id,
                project_id=artifact.project_id,
                workspace_id=artifact.workspace_id,
                name=artifact.name,
                source_path=artifact.source_path,
                size=artifact.size,
                file_count=artifact.file_count,
                content_hash=artifact.content_hash,
                status=artifact.status.value,
                description=artifact.description,
                created_at=artifact.created_at or datetime.now(UTC),
                cleaned_at=artifact.cleaned_at,
            )
        )
        await _flush(self._session)

    async def get(self, artifact_id: str) -> Artifact | None:
        row = await self._session.get(t.ArtifactRow, artifact_id)
        return _to_artifact(row) if row else None

    async def update(self, artifact: Artifact) -> None:
        row = await self._session.get(t.ArtifactRow, artifact.id)
        if row is None:
            return
        # Artifact 内容不可变（GR-203），只允许更新展示元数据和清理状态。
        row.name = artifact.name
        row.description = artifact.description
        row.status = artifact.status.value
        row.cleaned_at = artifact.cleaned_at
        await _flush(self._session)

    async def list_for_run(self, run_id: str) -> list[Artifact]:
        stmt = (
            select(t.ArtifactRow)
            .where(t.ArtifactRow.run_id == run_id)
            .order_by(t.ArtifactRow.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_artifact(row) for row in rows]


class ActivityRepositoryImpl:
    """活动仓储：只写不改，只按时间倒序读。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, activity: Activity) -> None:
        self._session.add(
            t.ActivityRow(
                id=activity.id,
                workspace_id=activity.workspace_id,
                project_id=activity.project_id,
                actor_id=activity.actor_id,
                actor_name=activity.actor_name,
                action=activity.action.value,
                target_type=activity.target_type.value,
                target_id=activity.target_id,
                target_name=activity.target_name,
                detail=activity.detail,
                created_at=activity.created_at,
            )
        )
        await _flush(self._session)

    async def list_for_workspace(self, workspace_id: str, page: PageRequest) -> Page[Activity]:
        stmt = (
            select(t.ActivityRow)
            .where(t.ActivityRow.workspace_id == workspace_id)
            .order_by(t.ActivityRow.created_at.desc(), t.ActivityRow.id.desc())
        )
        return await _paginate(self._session, stmt, page, _to_activity)

    async def list_for_project(self, project_id: str, page: PageRequest) -> Page[Activity]:
        stmt = (
            select(t.ActivityRow)
            .where(t.ActivityRow.project_id == project_id)
            .order_by(t.ActivityRow.created_at.desc(), t.ActivityRow.id.desc())
        )
        return await _paginate(self._session, stmt, page, _to_activity)


def _to_activity(row: t.ActivityRow) -> Activity:
    return Activity(
        id=row.id,
        workspace_id=row.workspace_id,
        project_id=row.project_id,
        actor_id=row.actor_id,
        actor_name=row.actor_name,
        action=ActivityAction(row.action),
        target_type=TargetType(row.target_type),
        target_id=row.target_id,
        target_name=row.target_name,
        detail=row.detail,
        # SQLite 读回来的时间没有时区。不补的话 Pydantic 序列化出来不带 Z，
        # 前端会按本地时区解析，「刚刚」就变成了「8 小时前」。
        created_at=_required(row.created_at),
    )


class NotificationRepositoryImpl:
    """通知仓储。

    所有查询都带 ``recipient_id`` 条件——包括标记已读。
    少一个条件就是「能标记别人的通知」这种越权。
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, notification: Notification) -> None:
        self._session.add(
            t.NotificationRow(
                id=notification.id,
                recipient_id=notification.recipient_id,
                type=notification.type.value,
                title=notification.title,
                body=notification.body,
                workspace_id=notification.workspace_id,
                target_type=notification.target_type.value if notification.target_type else None,
                target_id=notification.target_id,
                mandatory=notification.mandatory,
                created_at=notification.created_at,
                read_at=notification.read_at,
            )
        )
        await _flush(self._session)

    async def list_for_user(
        self, user_id: str, page: PageRequest, *, unread_only: bool = False
    ) -> Page[Notification]:
        stmt = select(t.NotificationRow).where(t.NotificationRow.recipient_id == user_id)
        if unread_only:
            stmt = stmt.where(t.NotificationRow.read_at.is_(None))
        stmt = stmt.order_by(t.NotificationRow.created_at.desc(), t.NotificationRow.id.desc())
        return await _paginate(self._session, stmt, page, _to_notification)

    async def count_unread(self, user_id: str) -> int:
        total = (
            await self._session.execute(
                select(func.count())
                .select_from(t.NotificationRow)
                .where(
                    t.NotificationRow.recipient_id == user_id,
                    t.NotificationRow.read_at.is_(None),
                )
            )
        ).scalar_one()
        return int(total)

    async def mark_read(self, user_id: str, notification_id: str, at: datetime) -> bool:
        result = await self._session.execute(
            update(t.NotificationRow)
            .where(
                t.NotificationRow.id == notification_id,
                # 收件人条件不能省：否则任何人拿到别人的通知 ID 就能替他标记已读。
                # 有测试守着（test_notifications.py::test_不能标记别人的通知）。
                t.NotificationRow.recipient_id == user_id,
                t.NotificationRow.read_at.is_(None),
            )
            .values(read_at=at)
        )
        return int(result.rowcount or 0) > 0

    async def mark_all_read(self, user_id: str, at: datetime) -> int:
        result = await self._session.execute(
            update(t.NotificationRow)
            .where(
                t.NotificationRow.recipient_id == user_id,
                t.NotificationRow.read_at.is_(None),
            )
            .values(read_at=at)
        )
        return int(result.rowcount or 0)


def _to_notification(row: t.NotificationRow) -> Notification:
    return Notification(
        id=row.id,
        recipient_id=row.recipient_id,
        type=NotificationType(row.type),
        title=row.title,
        body=row.body,
        workspace_id=row.workspace_id,
        target_type=TargetType(row.target_type) if row.target_type else None,
        target_id=row.target_id,
        mandatory=row.mandatory,
        # 时区必须补，否则前端按本地时区解析（Issue 3 踩过）
        created_at=_required(row.created_at),
        read_at=_aware(row.read_at),
    )


class ForkRelationRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, relation: ForkRelation) -> None:
        self._session.add(
            t.ForkRelationRow(
                id=relation.id,
                project_id=relation.project_id,
                source_project_id=relation.source_project_id,
                source_version_id=relation.source_version_id,
                source_workspace_id=relation.source_workspace_id,
                source_project_name=relation.source_project_name,
                source_version_label=relation.source_version_label,
                created_by=relation.created_by,
                created_at=relation.created_at,
            )
        )
        await _flush(self._session)

    async def get_for_project(self, project_id: str) -> ForkRelation | None:
        row = (
            await self._session.execute(
                select(t.ForkRelationRow).where(t.ForkRelationRow.project_id == project_id)
            )
        ).scalar_one_or_none()
        return _to_fork_relation(row) if row else None


def _to_fork_relation(row: t.ForkRelationRow) -> ForkRelation:
    return ForkRelation(
        id=row.id,
        project_id=row.project_id,
        source_project_id=row.source_project_id,
        source_version_id=row.source_version_id,
        source_workspace_id=row.source_workspace_id,
        source_project_name=row.source_project_name,
        source_version_label=row.source_version_label,
        created_by=row.created_by,
        created_at=_required(row.created_at),
    )


class SqlRepositories:
    """一次工作单元内的全部仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.users = UserRepositoryImpl(session)
        self.workspaces = WorkspaceRepositoryImpl(session)
        self.memberships = MembershipRepositoryImpl(session)
        self.variables = VariableRepositoryImpl(session)
        self.projects = ProjectRepositoryImpl(session)
        self.project_files = ProjectFileRepositoryImpl(session)
        self.project_versions = ProjectVersionRepositoryImpl(session)
        self.environments = EnvironmentRepositoryImpl(session)
        self.compute_plans = ComputePlanRepositoryImpl(session)
        self.entitlements = EntitlementRepositoryImpl(session)
        self.run_configurations = RunConfigurationRepositoryImpl(session)
        self.run_snapshots = RunSnapshotRepositoryImpl(session)
        self.runs = RunRepositoryImpl(session)
        self.execution_intents = ExecutionIntentRepositoryImpl(session)
        self.run_events = RunEventRepositoryImpl(session)
        self.idempotency = IdempotencyRepositoryImpl(session)
        self.artifacts = ArtifactRepositoryImpl(session)
        self.activities = ActivityRepositoryImpl(session)
        self.notifications = NotificationRepositoryImpl(session)
        self.fork_relations = ForkRelationRepositoryImpl(session)

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def ping(self) -> None:
        await self._session.execute(text("SELECT 1"))


# --------------------------------------------------------------------------
# 行 -> 领域对象
# --------------------------------------------------------------------------


def _visible_workspace_ids(user_id: str):
    """按有效 Membership 返回当前用户可见的 Workspace（GR-102）。"""
    member_ids = select(t.MembershipRow.workspace_id).where(
        t.MembershipRow.user_id == user_id,
        t.MembershipRow.status == MembershipStatus.ACTIVE.value,
    )
    return select(t.WorkspaceRow.id).where(
        (t.WorkspaceRow.owner_id == user_id) | t.WorkspaceRow.id.in_(member_ids)
    )


def _to_user(row: t.UserRow) -> User:
    return User(
        id=row.id,
        username=row.username,
        display_name=row.display_name,
        email=row.email,
        created_at=_aware(row.created_at),
    )


def _to_workspace(row: t.WorkspaceRow) -> Workspace:
    return Workspace(
        id=row.id,
        kind=WorkspaceKind(row.kind),
        name=row.name,
        description=row.description,
        owner_id=row.owner_id,
        default_environment_version_id=row.default_environment_version_id,
        created_at=_aware(row.created_at),
    )


def _to_membership(row: t.MembershipRow) -> Membership:
    return Membership(
        id=row.id,
        workspace_id=row.workspace_id,
        user_id=row.user_id,
        role=WorkspaceRole(row.role),
        status=MembershipStatus(row.status),
        created_at=_aware(row.created_at),
    )


def _to_project(row: t.ProjectRow) -> Project:
    return Project(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        description=row.description,
        status=ProjectStatus(row.status),
        environment_version_id=row.environment_version_id,
        default_run_configuration_id=row.default_run_configuration_id,
        created_by=row.created_by,
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _to_project_file(row: t.ProjectFileRow) -> ProjectFile:
    return ProjectFile(
        project_id=row.project_id,
        path=row.path,
        size=row.size,
        content_hash=row.content_hash,
        updated_at=_aware(row.updated_at),
    )


def _to_environment_version(row: t.EnvironmentVersionRow) -> EnvironmentVersion:
    return EnvironmentVersion(
        id=row.id,
        environment_id=row.environment_id,
        version=row.version,
        description=row.description,
        image=row.image,
        setup_command=row.setup_command,
        available=row.available,
    )


def _to_compute_plan(row: t.ComputePlanRow) -> ComputePlan:
    return ComputePlan(
        id=row.id,
        code=row.code,
        name=row.name,
        description=row.description,
        default_nodes=row.default_nodes,
        default_cpus=row.default_cpus,
        default_memory_mb=row.default_memory_mb,
        default_gpus=row.default_gpus,
        default_time_limit_minutes=row.default_time_limit_minutes,
        max_nodes=row.max_nodes,
        max_cpus=row.max_cpus,
        max_memory_mb=row.max_memory_mb,
        max_gpus=row.max_gpus,
        max_time_limit_minutes=row.max_time_limit_minutes,
        mapping=SchedulerMapping(
            cluster=row.cluster,
            account=row.account,
            partition=row.partition,
            qos=row.qos,
        ),
    )


def _to_entitlement(row: t.ResourceEntitlementRow) -> ResourceEntitlement:
    return ResourceEntitlement(
        id=row.id,
        workspace_id=row.workspace_id,
        compute_plan_id=row.compute_plan_id,
        max_concurrent_runs=row.max_concurrent_runs,
        expires_at=row.expires_at,
    )


def _env_to_payload(configuration: RunConfiguration) -> dict[str, str]:
    return {name: value.expression for name, value in configuration.environment_variables.items()}


def _to_run_configuration(row: t.RunConfigurationRow) -> RunConfiguration:
    raw_env: dict[str, Any] = dict(row.environment_variables or {})
    return RunConfiguration(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        description=row.description,
        working_directory=row.working_directory,
        command=row.command,
        environment_version_id=row.environment_version_id,
        environment_variables={
            name: parse_env_value(str(value)) for name, value in raw_env.items()
        },
        input_bindings=tuple(
            InputBinding(
                source_type=InputSourceType(b["source_type"]),
                source_id=b["source_id"],
                access_path=b["access_path"],
                source_subpath=b.get("source_subpath", ""),
            )
            for b in (row.input_bindings or [])
        ),
        compute_plan_id=row.compute_plan_id,
        compute_request=(
            ComputeRequest(**row.compute_request) if row.compute_request is not None else None
        ),
        artifact_rules=tuple(
            ArtifactCollectionRule(
                path=r["path"], name=r.get("name", ""), optional=r.get("optional", True)
            )
            for r in (row.artifact_rules or [])
        ),
    )


def _to_run(row: t.RunRow) -> Run:
    return Run(
        id=row.id,
        project_id=row.project_id,
        workspace_id=row.workspace_id,
        snapshot_id=row.snapshot_id,
        compute_plan_id=row.compute_plan_id,
        source_run_configuration_id=row.source_run_configuration_id,
        source_run_id=row.source_run_id,
        name=row.name,
        status=RunStatus(row.status),
        scheduler_job_id=row.scheduler_job_id,
        exit_code=row.exit_code,
        failure_reason=row.failure_reason,
        created_by=row.created_by,
        created_at=_aware(row.created_at),
        submitted_at=_aware(row.submitted_at),
        started_at=_aware(row.started_at),
        finished_at=_aware(row.finished_at),
    )


def _to_artifact(row: t.ArtifactRow) -> Artifact:
    return Artifact(
        id=row.id,
        run_id=row.run_id,
        project_id=row.project_id,
        workspace_id=row.workspace_id,
        name=row.name,
        source_path=row.source_path,
        size=row.size,
        file_count=row.file_count,
        content_hash=row.content_hash,
        status=ArtifactStatus(row.status),
        description=row.description,
        created_at=_aware(row.created_at),
        cleaned_at=_aware(row.cleaned_at),
    )
