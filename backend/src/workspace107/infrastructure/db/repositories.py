"""基于 SQLAlchemy 的仓储实现。

行对象与领域对象在这里互相转换。application 层拿到的永远是领域对象，
不会看到 ``*Row``。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.compute import ComputePlan, ComputeRequest, ResourceEntitlement, SchedulerMapping
from ...domain.config_scope import ConfigScope
from ...domain.enums import (
    ActivityAction,
    ArtifactStatus,
    EnvironmentAvailability,
    EnvironmentPublicationStatus,
    EnvironmentRuntimeKind,
    InputSourceType,
    MembershipRole,
    MembershipStatus,
    NotificationType,
    ProjectStatus,
    ProjectVisibility,
    RunEventType,
    RunStatus,
    SharedResourcePublicationStatus,
    TargetType,
)
from ...domain.errors import ConflictError
from ...domain.grant import Grant, GrantAction, GrantTargetKind
from ...domain.models import (
    Activity,
    Artifact,
    ArtifactCollectionRule,
    Environment,
    EnvironmentPublicationAttempt,
    EnvironmentVersion,
    ForkRelation,
    IdempotencyRecord,
    InputBinding,
    Membership,
    Notification,
    NotificationPreference,
    Project,
    ProjectFile,
    ProjectVersion,
    ProjectVersionFile,
    Run,
    RunConfiguration,
    RunEvent,
    SharedResource,
    SharedResourceFile,
    SharedResourcePublicationAttempt,
    SharedResourceVersion,
    User,
    UserGroup,
    Variable,
)
from ...domain.ownership import OwnerKind, OwnerReference
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
    (
        ("uq_projects_owner_user_name", "uq_projects_owner_user_group_name", "projects.name"),
        "当前 Owner 中已存在同名 Project",
    ),
    (("uq_user_group_membership", "memberships.user_id"), "该用户已经是成员或已被邀请"),
    (("uq_membership_active_owner", "memberships.user_group_id"), "User Group 已有有效 Owner"),
    (
        ("uq_entitlement", "resource_entitlements.compute_plan_id"),
        "该 User 已经拥有这个算力方案的资源权益",
    ),
    (
        ("idempotency_keys_pkey", "idempotency_keys.key"),
        "相同的提交请求正在处理中，请稍后查看 Run 列表，不要重复提交",
    ),
    (
        ("uq_shared_resource_version_seq", "shared_resource_versions.sequence"),
        "有其他人同时发布了这个 Shared Resource 的版本，请刷新后重试",
    ),
    (
        ("uq_grant_grantor_grantee_target_action", "grants.grantor_id"),
        "该 Grantee 已拥有此 Grantor 的相应 USE Grant",
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

    async def list_by_ids(self, user_ids: set[str]) -> dict[str, User]:
        if not user_ids:
            return {}
        stmt = select(t.UserRow).where(t.UserRow.id.in_(user_ids))
        rows = (await self._session.execute(stmt)).scalars().all()
        return {row.id: _to_user(row) for row in rows}


class UserGroupRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user_group: UserGroup) -> None:
        self._session.add(
            t.UserGroupRow(
                id=user_group.id,
                name=user_group.name,
                description=user_group.description,
                created_by_id=user_group.created_by_id,
                created_at=user_group.created_at or datetime.now(UTC),
            )
        )
        await _flush(self._session)

    async def get(self, user_group_id: str) -> UserGroup | None:
        row = await self._session.get(t.UserGroupRow, user_group_id)
        return _to_user_group(row) if row else None

    async def get_for_update(self, user_group_id: str) -> UserGroup | None:
        # PostgreSQL locks this exact UserGroup row. SQLite ignores FOR UPDATE,
        # so acquire its transaction-wide write lock with an exact-row no-op
        # update before reading any Membership state.
        if self._session.bind and self._session.bind.dialect.name == "sqlite":
            await self._session.execute(
                update(t.UserGroupRow)
                .where(t.UserGroupRow.id == user_group_id)
                .values(id=t.UserGroupRow.id)
            )
        stmt = select(t.UserGroupRow).where(t.UserGroupRow.id == user_group_id).with_for_update()
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_user_group(row) if row else None

    async def get_for_active_member(self, user_group_id: str, user_id: str) -> UserGroup | None:
        stmt = (
            select(t.UserGroupRow)
            .join(
                t.MembershipRow,
                t.MembershipRow.user_group_id == t.UserGroupRow.id,
            )
            .where(
                t.UserGroupRow.id == user_group_id,
                t.MembershipRow.user_id == user_id,
                t.MembershipRow.status == MembershipStatus.ACTIVE.value,
            )
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_user_group(row) if row else None

    async def update(self, user_group: UserGroup) -> None:
        row = await self._session.get(t.UserGroupRow, user_group.id)
        if row is None:
            return
        row.name = user_group.name
        row.description = user_group.description
        await _flush(self._session)

    async def list_for_user(self, user_id: str) -> list[UserGroup]:
        group_ids = select(t.MembershipRow.user_group_id).where(
            t.MembershipRow.user_id == user_id,
            t.MembershipRow.status == MembershipStatus.ACTIVE.value,
        )
        stmt = (
            select(t.UserGroupRow)
            .where(t.UserGroupRow.id.in_(group_ids))
            .order_by(t.UserGroupRow.created_at, t.UserGroupRow.id)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_user_group(row) for row in rows]

    async def list_by_ids(self, user_group_ids: set[str]) -> dict[str, UserGroup]:
        if not user_group_ids:
            return {}
        stmt = select(t.UserGroupRow).where(t.UserGroupRow.id.in_(user_group_ids))
        rows = (await self._session.execute(stmt)).scalars().all()
        return {row.id: _to_user_group(row) for row in rows}


class MembershipRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, membership: Membership) -> None:
        self._session.add(
            t.MembershipRow(
                id=membership.id,
                user_group_id=membership.user_group_id,
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

    async def get(self, user_group_id: str, user_id: str) -> Membership | None:
        stmt = select(t.MembershipRow).where(
            t.MembershipRow.user_group_id == user_group_id,
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

    async def list_for_user_group(self, user_group_id: str) -> list[Membership]:
        stmt = (
            select(t.MembershipRow)
            .where(
                t.MembershipRow.user_group_id == user_group_id,
                t.MembershipRow.status.in_(
                    [MembershipStatus.ACTIVE.value, MembershipStatus.INVITED.value]
                ),
            )
            .order_by(t.MembershipRow.created_at, t.MembershipRow.id)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_membership(row) for row in rows]

    async def get_active_owner(self, user_group_id: str) -> Membership | None:
        stmt = select(t.MembershipRow).where(
            t.MembershipRow.user_group_id == user_group_id,
            t.MembershipRow.role == MembershipRole.OWNER.value,
            t.MembershipRow.status == MembershipStatus.ACTIVE.value,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_membership(row) if row else None


class VariableRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_scope(self, scope: ConfigScope) -> list[Variable]:
        stmt = (
            select(t.VariableRow)
            .where(t.VariableRow.scope_kind == scope.kind.value, t.VariableRow.scope_id == scope.id)
            .order_by(t.VariableRow.name)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [Variable(scope=scope, name=r.name, value=r.value) for r in rows]

    async def get(self, scope: ConfigScope, name: str) -> Variable | None:
        row = await self._session.get(t.VariableRow, (scope.kind.value, scope.id, name))
        return Variable(scope=scope, name=row.name, value=row.value) if row else None

    async def upsert(self, variable: Variable) -> None:
        key = (variable.scope.kind.value, variable.scope.id, variable.name)
        row = await self._session.get(t.VariableRow, key)
        if row is None:
            self._session.add(
                t.VariableRow(
                    scope_kind=variable.scope.kind.value,
                    scope_id=variable.scope.id,
                    name=variable.name,
                    value=variable.value,
                )
            )
        else:
            row.value = variable.value
        await _flush(self._session)

    async def delete(self, scope: ConfigScope, name: str) -> None:
        await self._session.execute(
            delete(t.VariableRow).where(
                t.VariableRow.scope_kind == scope.kind.value,
                t.VariableRow.scope_id == scope.id,
                t.VariableRow.name == name,
            )
        )
        await _flush(self._session)


class ProjectRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, project: Project) -> None:
        owner_user_id, owner_user_group_id = _owner_columns(project.owner)
        self._session.add(
            t.ProjectRow(
                id=project.id,
                owner_user_id=owner_user_id,
                owner_user_group_id=owner_user_group_id,
                name=project.name,
                description=project.description,
                status=project.status.value,
                visibility=project.visibility.value,
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
        owner_user_id, owner_user_group_id = _owner_columns(project.owner)
        row.name = project.name
        row.owner_user_id = owner_user_id
        row.owner_user_group_id = owner_user_group_id
        row.description = project.description
        row.status = project.status.value
        row.visibility = project.visibility.value
        row.environment_version_id = project.environment_version_id
        row.default_run_configuration_id = project.default_run_configuration_id
        row.updated_at = project.updated_at or datetime.now(UTC)
        await _flush(self._session)

    async def list_for_user(self, user_id: str, *, limit: int) -> list[Project]:
        # Owner-scope only (no PUBLIC discovery): /me recent_projects shows what
        # the User owns or their User Groups own.
        group_ids = select(t.MembershipRow.user_group_id).where(
            t.MembershipRow.user_id == user_id,
            t.MembershipRow.status == MembershipStatus.ACTIVE.value,
        )
        stmt = (
            select(t.ProjectRow)
            .where(
                (t.ProjectRow.owner_user_id == user_id)
                | t.ProjectRow.owner_user_group_id.in_(group_ids)
            )
            .order_by(t.ProjectRow.updated_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_project(row) for row in rows]

    async def list_discoverable_for_user(
        self,
        user_id: str,
        page: PageRequest,
        *,
        owner: OwnerReference | None = None,
        query: str | None = None,
    ) -> Page[Project]:
        # Owner scope + PUBLIC projects the User can discover.
        group_ids = select(t.MembershipRow.user_group_id).where(
            t.MembershipRow.user_id == user_id,
            t.MembershipRow.status == MembershipStatus.ACTIVE.value,
        )
        owner_scope = (
            t.ProjectRow.owner_user_id == user_id
        ) | t.ProjectRow.owner_user_group_id.in_(group_ids)
        stmt = select(t.ProjectRow).where(
            (t.ProjectRow.visibility == ProjectVisibility.PUBLIC.value) | owner_scope
        )
        if owner is not None:
            owner_column = (
                t.ProjectRow.owner_user_id
                if owner.kind is OwnerKind.USER
                else t.ProjectRow.owner_user_group_id
            )
            stmt = stmt.where(owner_column == owner.id)
        normalized_query = query.strip() if query else ""
        if normalized_query:
            stmt = stmt.where(t.ProjectRow.name.icontains(normalized_query, autoescape=True))
        stmt = stmt.order_by(t.ProjectRow.updated_at.desc())
        return await _paginate(self._session, stmt, page, _to_project)

    async def list_using_environment_version(self, version_id: str) -> list[Project]:
        config_projects = select(t.RunConfigurationRow.project_id).where(
            t.RunConfigurationRow.environment_version_id == version_id
        )
        snapshot_projects = (
            select(t.RunRow.project_id)
            .join(
                t.RunSnapshotEnvironmentReferenceRow,
                t.RunSnapshotEnvironmentReferenceRow.snapshot_id == t.RunRow.snapshot_id,
            )
            .where(t.RunSnapshotEnvironmentReferenceRow.environment_version_id == version_id)
        )
        stmt = select(t.ProjectRow).where(
            (t.ProjectRow.environment_version_id == version_id)
            | t.ProjectRow.id.in_(config_projects)
            | t.ProjectRow.id.in_(snapshot_projects)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_project(row) for row in rows]

    async def name_exists(self, owner: OwnerReference, name: str) -> bool:
        owner_column = (
            t.ProjectRow.owner_user_id
            if owner.kind is OwnerKind.USER
            else t.ProjectRow.owner_user_group_id
        )
        stmt = (
            select(func.count())
            .select_from(t.ProjectRow)
            .where(owner_column == owner.id, t.ProjectRow.name == name)
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

    async def list_discoverable_for_user(self, user_id: str) -> list[Environment]:
        stmt = (
            select(t.EnvironmentRow)
            .where(
                _asset_discovery_predicate(
                    t.EnvironmentRow.owner_user_id,
                    t.EnvironmentRow.owner_user_group_id,
                    user_id,
                )
            )
            .order_by(t.EnvironmentRow.name)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_environment(row) for row in rows]

    async def get_discoverable_for_user(
        self, user_id: str, environment_id: str
    ) -> Environment | None:
        stmt = select(t.EnvironmentRow).where(
            t.EnvironmentRow.id == environment_id,
            _asset_discovery_predicate(
                t.EnvironmentRow.owner_user_id,
                t.EnvironmentRow.owner_user_group_id,
                user_id,
            ),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_environment(row) if row else None

    async def list_versions_discoverable_for_user(
        self, user_id: str, environment_id: str
    ) -> list[EnvironmentVersion]:
        stmt = (
            select(t.EnvironmentVersionRow)
            .join(
                t.EnvironmentRow,
                t.EnvironmentRow.id == t.EnvironmentVersionRow.environment_id,
            )
            .where(
                t.EnvironmentRow.id == environment_id,
                _asset_discovery_predicate(
                    t.EnvironmentRow.owner_user_id,
                    t.EnvironmentRow.owner_user_group_id,
                    user_id,
                ),
            )
            .order_by(t.EnvironmentVersionRow.version)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_environment_version(row) for row in rows]

    async def get_version_discoverable_for_user(
        self, user_id: str, version_id: str
    ) -> EnvironmentVersion | None:
        stmt = (
            select(t.EnvironmentVersionRow)
            .join(
                t.EnvironmentRow,
                t.EnvironmentRow.id == t.EnvironmentVersionRow.environment_id,
            )
            .where(
                t.EnvironmentVersionRow.id == version_id,
                _asset_discovery_predicate(
                    t.EnvironmentRow.owner_user_id,
                    t.EnvironmentRow.owner_user_group_id,
                    user_id,
                ),
            )
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_environment_version(row) if row else None

    async def list_for_owner(self, owner: OwnerReference) -> list[Environment]:
        owner_user_id, owner_group_id = _owner_columns(owner)
        stmt = (
            select(t.EnvironmentRow)
            .where(
                t.EnvironmentRow.owner_user_id == owner_user_id,
                t.EnvironmentRow.owner_user_group_id == owner_group_id,
            )
            .order_by(t.EnvironmentRow.name, t.EnvironmentRow.id)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_environment(row) for row in rows]

    async def list_versions(self, environment_id: str) -> list[EnvironmentVersion]:
        stmt = (
            select(t.EnvironmentVersionRow)
            .where(t.EnvironmentVersionRow.environment_id == environment_id)
            .order_by(t.EnvironmentVersionRow.version.desc(), t.EnvironmentVersionRow.id)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_environment_version(row) for row in rows]

    async def get_version_by_id(self, version_id: str) -> EnvironmentVersion | None:
        """Trusted exact lookup for grant-authorized use."""
        row = await self._session.get(t.EnvironmentVersionRow, version_id)
        return _to_environment_version(row) if row else None

    async def get_by_id(self, environment_id: str) -> Environment | None:
        """Trusted exact lookup for grant-authorized use."""
        row = await self._session.get(t.EnvironmentRow, environment_id)
        return _to_environment(row) if row else None

    async def add_version(self, version: EnvironmentVersion) -> None:
        self._session.add(
            t.EnvironmentVersionRow(
                id=version.id,
                environment_id=version.environment_id,
                version=version.version,
                description=version.description,
                runtime_kind=version.runtime_kind.value,
                definition=version.definition,
                definition_hash=version.definition_hash,
                execution_spec=version.execution_spec,
                validation_summary=version.validation_summary,
                validation_evidence=version.validation_evidence,
                availability=version.availability.value,
                availability_reason=version.availability_reason,
                availability_detail=version.availability_detail,
                availability_checked_at=version.availability_checked_at,
            )
        )
        await self._session.flush()

    async def add_attempt(self, attempt: EnvironmentPublicationAttempt) -> None:
        self._session.add(_environment_attempt_row(attempt))
        await self._session.flush()

    async def update_attempt(self, attempt: EnvironmentPublicationAttempt) -> None:
        row = await self._session.get(t.EnvironmentPublicationAttemptRow, attempt.id)
        if row is None:
            return
        for name in (
            "status",
            "validation_summary",
            "validation_evidence",
            "failure_code",
            "failure_reason",
            "version_id",
            "started_at",
            "finished_at",
        ):
            value = getattr(attempt, name)
            setattr(row, name, value.value if hasattr(value, "value") else value)
        await self._session.flush()

    async def get_attempt_by_id(self, attempt_id: str) -> EnvironmentPublicationAttempt | None:
        row = await self._session.get(t.EnvironmentPublicationAttemptRow, attempt_id)
        return _to_environment_attempt(row) if row else None

    async def list_attempts_discoverable_for_user(
        self, user_id: str, environment_id: str
    ) -> list[EnvironmentPublicationAttempt]:
        stmt = (
            select(t.EnvironmentPublicationAttemptRow)
            .join(
                t.EnvironmentRow,
                t.EnvironmentRow.id == t.EnvironmentPublicationAttemptRow.environment_id,
            )
            .where(
                t.EnvironmentPublicationAttemptRow.environment_id == environment_id,
                _asset_discovery_predicate(
                    t.EnvironmentRow.owner_user_id,
                    t.EnvironmentRow.owner_user_group_id,
                    user_id,
                ),
            )
            .order_by(t.EnvironmentPublicationAttemptRow.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_environment_attempt(row) for row in rows]

    async def update_version_availability(
        self,
        version_id: str,
        availability: EnvironmentAvailability,
        reason: str,
        detail: str,
        checked_at: datetime,
    ) -> EnvironmentVersion | None:
        row = await self._session.get(t.EnvironmentVersionRow, version_id)
        if row is None:
            return None
        row.availability = availability.value
        row.availability_reason = reason
        row.availability_detail = detail
        row.availability_checked_at = checked_at
        await self._session.flush()
        return _to_environment_version(row)

    async def claim_pending_attempt(self, now: datetime) -> EnvironmentPublicationAttempt | None:
        stmt = (
            select(t.EnvironmentPublicationAttemptRow)
            .where(t.EnvironmentPublicationAttemptRow.status.in_(["pending", "processing"]))
            .order_by(t.EnvironmentPublicationAttemptRow.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        row.status = EnvironmentPublicationStatus.PROCESSING.value
        row.started_at = now
        await self._session.flush()
        return _to_environment_attempt(row)


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

    async def list_for_user(self, user_id: str) -> list[ResourceEntitlement]:
        stmt = select(t.ResourceEntitlementRow).where(t.ResourceEntitlementRow.user_id == user_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_entitlement(r) for r in rows]

    async def get_for_plan(self, user_id: str, compute_plan_id: str) -> ResourceEntitlement | None:
        stmt = select(t.ResourceEntitlementRow).where(
            t.ResourceEntitlementRow.user_id == user_id,
            t.ResourceEntitlementRow.compute_plan_id == compute_plan_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_entitlement(row) if row else None

    async def add(self, entitlement: ResourceEntitlement) -> None:
        self._session.add(
            t.ResourceEntitlementRow(
                id=entitlement.id,
                user_id=entitlement.user_id,
                compute_plan_id=entitlement.compute_plan_id,
                max_concurrent_runs=entitlement.max_concurrent_runs,
                expires_at=entitlement.expires_at,
            )
        )
        await _flush(self._session)

    async def lock_for_plan(self, user_id: str, compute_plan_id: str) -> ResourceEntitlement | None:
        """SELECT ... FOR UPDATE，锁到事务结束。

        PostgreSQL 上这行会被真正独占，第二个并发请求阻塞到第一个提交为止。
        SQLite 不支持 FOR UPDATE，SQLAlchemy 的方言会忽略它——开发和测试环境
        依赖 SQLite 自身的写串行化，生产环境（PostgreSQL）才有严格保证。
        """
        stmt = (
            select(t.ResourceEntitlementRow)
            .where(
                t.ResourceEntitlementRow.user_id == user_id,
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
        self._session.add(
            t.RunSnapshotEnvironmentReferenceRow(
                snapshot_id=snapshot.id,
                environment_version_id=snapshot.environment_version_id,
            )
        )
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
                snapshot_id=run.snapshot_id,
                compute_plan_id=run.compute_plan_id,
                project_version_id=run.project_version_id,
                project_version_label=run.project_version_label,
                source_run_configuration_id=run.source_run_configuration_id,
                source_run_id=run.source_run_id,
                name=run.name,
                status=run.status.value,
                scheduler_job_id=run.scheduler_job_id,
                exit_code=run.exit_code,
                failure_reason=run.failure_reason,
                initiated_by_user_id=run.initiated_by_user_id,
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
        # Home recent Runs are personal execution history: the User must be both the
        # initiator and currently able to see the owning Project.
        group_ids = select(t.MembershipRow.user_group_id).where(
            t.MembershipRow.user_id == user_id,
            t.MembershipRow.status == MembershipStatus.ACTIVE.value,
        )
        stmt = (
            select(t.RunRow)
            .join(t.ProjectRow, t.ProjectRow.id == t.RunRow.project_id)
            .where(
                t.RunRow.initiated_by_user_id == user_id,
                (t.ProjectRow.owner_user_id == user_id)
                | t.ProjectRow.owner_user_group_id.in_(group_ids),
            )
            .order_by(t.RunRow.created_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_run(row) for row in rows]

    async def list_unfinished(self) -> list[Run]:
        stmt = select(t.RunRow).where(
            t.RunRow.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value])
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_run(row) for row in rows]

    async def claim_terminal(self, run: Run) -> bool:
        """把 Run 从「未结束」推进到终态，成功抢到返回 True。

        条件更新，不是先查后写：两次并发同步会同时读到 queued/running，
        各自无条件写入的话产物会被收集两遍。谁的 UPDATE 命中了行谁负责收产物，
        另一个拿到 rowcount=0 直接退出。

        只更新状态相关的几列，其余字段由调用方随后的 update 写——
        收产物可能还会把状态改成 failed。
        """
        result = await self._session.execute(
            update(t.RunRow)
            .where(
                t.RunRow.id == run.id,
                t.RunRow.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value]),
            )
            .values(
                status=run.status.value,
                exit_code=run.exit_code,
                failure_reason=run.failure_reason,
                started_at=run.started_at,
                finished_at=run.finished_at,
            )
        )
        return int(result.rowcount or 0) == 1

    async def count_unfinished_for_plan(self, user_id: str, compute_plan_id: str) -> int:
        """数「这个 User 在这个算力方案上」还有几个未结束的 Run。

        并发额度按「User × 方案」授予，锁的也是那个 User 的那一条权益行，
        所以只数该 User 发起（initiated_by_user_id）的 Run。**计数范围大于
        加锁范围就等于没锁**——计数范围里混进别人的 Run，会读出一个比实际
        大的数，让本来还有名额的请求被误拒，或反过来。
        """
        stmt = (
            select(func.count())
            .select_from(t.RunRow)
            .where(
                t.RunRow.initiated_by_user_id == user_id,
                t.RunRow.compute_plan_id == compute_plan_id,
                t.RunRow.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value]),
            )
        )
        return int((await self._session.execute(stmt)).scalar_one())


class IdempotencyRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find(self, user_id: str, key: str) -> IdempotencyRecord | None:
        row = await self._session.get(t.IdempotencyKeyRow, (user_id, key))
        if row is None:
            return None
        return IdempotencyRecord(
            initiated_by_user_id=row.initiated_by_user_id,
            key=row.key,
            endpoint=row.endpoint,
            run_id=row.run_id,
            created_at=_required(row.created_at),
        )

    async def reserve(self, user_id: str, key: str, endpoint: str) -> None:
        """登记这个 key 并立刻落库。

        立刻 flush 是关键：复合主键的冲突要在这一刻就暴露出来，
        而不是等到请求末尾——那时候作业已经提交给调度系统了。
        """
        self._session.add(
            t.IdempotencyKeyRow(
                initiated_by_user_id=user_id,
                key=key,
                endpoint=endpoint,
                run_id=None,
                created_at=datetime.now(UTC),
            )
        )
        await _flush(self._session)

    async def attach_run(self, user_id: str, key: str, run_id: str) -> None:
        row = await self._session.get(t.IdempotencyKeyRow, (user_id, key))
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
    """Append-only activity persistence scoped by current Owner authority."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, activity: Activity) -> None:
        owner_user_id, owner_user_group_id = _owner_columns(activity.owner)
        self._session.add(
            t.ActivityRow(
                id=activity.id,
                owner_user_id=owner_user_id,
                owner_user_group_id=owner_user_group_id,
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

    async def list_for_owner(self, owner: OwnerReference, page: PageRequest) -> Page[Activity]:
        owner_column = (
            t.ActivityRow.owner_user_id
            if owner.kind is OwnerKind.USER
            else t.ActivityRow.owner_user_group_id
        )
        stmt = (
            select(t.ActivityRow)
            .where(owner_column == owner.id)
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
        owner=_owner_reference(row.owner_user_id, row.owner_user_group_id),
        project_id=row.project_id,
        actor_id=row.actor_id,
        actor_name=row.actor_name,
        action=ActivityAction(row.action),
        target_type=TargetType(row.target_type),
        target_id=row.target_id,
        target_name=row.target_name,
        detail=row.detail,
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

    async def mark_unread(self, user_id: str, notification_id: str) -> bool:
        result = await self._session.execute(
            update(t.NotificationRow)
            .where(
                t.NotificationRow.id == notification_id,
                t.NotificationRow.recipient_id == user_id,
                t.NotificationRow.read_at.is_not(None),
            )
            .values(read_at=None)
        )
        return int(result.rowcount or 0) > 0

    async def is_enabled(self, user_id: str, type: NotificationType) -> bool:
        row = await self._session.get(t.NotificationPreferenceRow, (user_id, type.value))
        return row is None or row.enabled

    async def list_preferences(self, user_id: str) -> list[NotificationPreference]:
        stmt = select(t.NotificationPreferenceRow).where(
            t.NotificationPreferenceRow.user_id == user_id
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            NotificationPreference(
                user_id=row.user_id,
                type=NotificationType(row.notification_type),
                enabled=row.enabled,
            )
            for row in rows
        ]

    async def set_preference(
        self, user_id: str, type: NotificationType, enabled: bool
    ) -> NotificationPreference:
        row = await self._session.get(t.NotificationPreferenceRow, (user_id, type.value))
        if row is None:
            self._session.add(
                t.NotificationPreferenceRow(
                    user_id=user_id,
                    notification_type=type.value,
                    enabled=enabled,
                )
            )
        else:
            row.enabled = enabled
        await _flush(self._session)
        return NotificationPreference(user_id=user_id, type=type, enabled=enabled)

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
        source_owner_user_id, source_owner_user_group_id = _owner_columns(relation.source_owner)
        self._session.add(
            t.ForkRelationRow(
                id=relation.id,
                project_id=relation.project_id,
                source_project_id=relation.source_project_id,
                source_version_id=relation.source_version_id,
                source_owner_user_id=source_owner_user_id,
                source_owner_user_group_id=source_owner_user_group_id,
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
        source_owner=_owner_reference(row.source_owner_user_id, row.source_owner_user_group_id),
        source_project_name=row.source_project_name,
        source_version_label=row.source_version_label,
        created_by=row.created_by,
        created_at=_required(row.created_at),
    )


class SharedResourceRepositoryImpl:
    """Shared Resource persistence with owner-scoped public discovery."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, resource: SharedResource) -> None:
        owner_user_id, owner_user_group_id = _owner_columns(resource.owner)
        self._session.add(
            t.SharedResourceRow(
                id=resource.id,
                name=resource.name,
                description=resource.description,
                owner_user_id=owner_user_id,
                owner_user_group_id=owner_user_group_id,
                created_at=resource.created_at or datetime.now(UTC),
            )
        )
        await _flush(self._session)

    async def update(self, resource: SharedResource) -> None:
        row = await self._session.get(t.SharedResourceRow, resource.id)
        if row is None:
            return
        row.name = resource.name
        row.description = resource.description
        await _flush(self._session)

    async def list_discoverable_for_user(self, user_id: str) -> list[SharedResource]:
        stmt = (
            select(t.SharedResourceRow)
            .where(_shared_resource_discovery_predicate(user_id))
            .order_by(t.SharedResourceRow.name)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_shared_resource(row) for row in rows]

    async def get_discoverable_for_user(
        self, user_id: str, resource_id: str
    ) -> SharedResource | None:
        stmt = select(t.SharedResourceRow).where(
            t.SharedResourceRow.id == resource_id,
            _shared_resource_discovery_predicate(user_id),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_shared_resource(row) if row else None

    async def add_attempt(self, attempt: SharedResourcePublicationAttempt) -> None:
        self._session.add(
            t.SharedResourcePublicationAttemptRow(
                id=attempt.id,
                shared_resource_id=attempt.shared_resource_id,
                status=attempt.status.value,
                description=attempt.description,
                validation_summary=attempt.validation_summary,
                failure_reason=attempt.failure_reason,
                version_id=attempt.version_id,
                created_by=attempt.created_by,
                created_at=attempt.created_at,
                started_at=attempt.started_at,
                finished_at=attempt.finished_at,
            )
        )
        await _flush(self._session)
        for entry in attempt.files:
            self._session.add(
                t.SharedResourcePublicationFileRow(
                    attempt_id=attempt.id,
                    path=entry.path,
                    size=entry.size,
                    content_hash=entry.content_hash,
                )
            )
        await _flush(self._session)

    async def update_attempt(self, attempt: SharedResourcePublicationAttempt) -> None:
        row = await self._session.get(t.SharedResourcePublicationAttemptRow, attempt.id)
        if row is None:
            return
        row.status = attempt.status.value
        row.validation_summary = attempt.validation_summary
        row.failure_reason = attempt.failure_reason
        row.version_id = attempt.version_id
        row.started_at = attempt.started_at
        row.finished_at = attempt.finished_at
        await _flush(self._session)

    async def claim_next_attempt(
        self, *, now: datetime, recover_before: datetime
    ) -> SharedResourcePublicationAttempt | None:
        stmt = (
            select(t.SharedResourcePublicationAttemptRow)
            .where(
                or_(
                    t.SharedResourcePublicationAttemptRow.status
                    == SharedResourcePublicationStatus.PENDING.value,
                    and_(
                        t.SharedResourcePublicationAttemptRow.status
                        == SharedResourcePublicationStatus.PROCESSING.value,
                        t.SharedResourcePublicationAttemptRow.started_at <= recover_before,
                    ),
                )
            )
            .order_by(t.SharedResourcePublicationAttemptRow.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        row.status = SharedResourcePublicationStatus.PROCESSING.value
        row.validation_summary = "正在校验候选内容"
        row.started_at = now
        await _flush(self._session)
        return await self._hydrate_attempt(row)

    async def get_attempt_discoverable_for_user(
        self, user_id: str, attempt_id: str
    ) -> SharedResourcePublicationAttempt | None:
        stmt = (
            select(t.SharedResourcePublicationAttemptRow)
            .join(
                t.SharedResourceRow,
                t.SharedResourceRow.id == t.SharedResourcePublicationAttemptRow.shared_resource_id,
            )
            .where(
                t.SharedResourcePublicationAttemptRow.id == attempt_id,
                _asset_discovery_predicate(
                    t.SharedResourceRow.owner_user_id,
                    t.SharedResourceRow.owner_user_group_id,
                    user_id,
                ),
            )
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return await self._hydrate_attempt(row) if row else None

    async def get_attempt_by_id(self, attempt_id: str) -> SharedResourcePublicationAttempt | None:
        row = await self._session.get(t.SharedResourcePublicationAttemptRow, attempt_id)
        return await self._hydrate_attempt(row) if row else None

    async def add_version(self, version: SharedResourceVersion) -> None:
        self._session.add(
            t.SharedResourceVersionRow(
                id=version.id,
                shared_resource_id=version.shared_resource_id,
                sequence=version.sequence,
                description=version.description,
                manifest_hash=version.manifest_hash,
                validation_summary=version.validation_summary,
                created_by=version.created_by,
                created_at=version.created_at,
            )
        )
        # 先把版本行落库，再插文件行——和 ProjectVersionRepositoryImpl 同样原因：
        # 这两张表只有外键，没有 ORM relationship，SQLAlchemy 不知道先后依赖，
        # SQLite 默认不校验外键时本地测试看不出来，到 PostgreSQL 上会 ForeignKeyViolation。
        await _flush(self._session)

        for entry in version.files:
            self._session.add(
                t.SharedResourceVersionFileRow(
                    version_id=version.id,
                    path=entry.path,
                    size=entry.size,
                    content_hash=entry.content_hash,
                )
            )
        await _flush(self._session)

    async def get_version_discoverable_for_user(
        self, user_id: str, version_id: str
    ) -> SharedResourceVersion | None:
        stmt = (
            select(t.SharedResourceVersionRow)
            .join(
                t.SharedResourceRow,
                t.SharedResourceRow.id == t.SharedResourceVersionRow.shared_resource_id,
            )
            .where(
                t.SharedResourceVersionRow.id == version_id,
                _shared_resource_discovery_predicate(user_id),
            )
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return await self._hydrate_version(row) if row else None

    async def get_version_by_id(self, version_id: str) -> SharedResourceVersion | None:
        row = await self._session.get(t.SharedResourceVersionRow, version_id)
        return await self._hydrate_version(row) if row else None

    async def get_by_id(self, resource_id: str) -> SharedResource | None:
        """Trusted exact lookup for grant-authorized use."""
        row = await self._session.get(t.SharedResourceRow, resource_id)
        return _to_shared_resource(row) if row else None

    async def list_versions_discoverable_for_user(
        self, user_id: str, resource_id: str
    ) -> list[SharedResourceVersion]:
        stmt = (
            select(t.SharedResourceVersionRow)
            .join(
                t.SharedResourceRow,
                t.SharedResourceRow.id == t.SharedResourceVersionRow.shared_resource_id,
            )
            .where(
                t.SharedResourceRow.id == resource_id,
                _shared_resource_discovery_predicate(user_id),
            )
            .order_by(t.SharedResourceVersionRow.sequence.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [await self._hydrate_version(row) for row in rows]

    async def next_version_sequence_for_publication(self, resource_id: str) -> int:
        # Serialize publication per Shared Resource before deriving the aggregate sequence.
        await self._session.execute(
            select(t.SharedResourceRow.id)
            .where(t.SharedResourceRow.id == resource_id)
            .with_for_update()
        )
        stmt = select(func.max(t.SharedResourceVersionRow.sequence)).where(
            t.SharedResourceVersionRow.shared_resource_id == resource_id
        )
        current = (await self._session.execute(stmt)).scalar_one_or_none()
        return int(current or 0) + 1

    async def _hydrate_version(self, row: t.SharedResourceVersionRow) -> SharedResourceVersion:
        stmt = (
            select(t.SharedResourceVersionFileRow)
            .where(t.SharedResourceVersionFileRow.version_id == row.id)
            .order_by(t.SharedResourceVersionFileRow.path)
        )
        files = (await self._session.execute(stmt)).scalars().all()
        return SharedResourceVersion(
            id=row.id,
            shared_resource_id=row.shared_resource_id,
            sequence=row.sequence,
            description=row.description,
            files=tuple(
                SharedResourceFile(path=f.path, size=f.size, content_hash=f.content_hash)
                for f in files
            ),
            manifest_hash=row.manifest_hash,
            validation_summary=row.validation_summary,
            created_by=row.created_by,
            created_at=_required(row.created_at),
        )

    async def _hydrate_attempt(
        self, row: t.SharedResourcePublicationAttemptRow
    ) -> SharedResourcePublicationAttempt:
        stmt = (
            select(t.SharedResourcePublicationFileRow)
            .where(t.SharedResourcePublicationFileRow.attempt_id == row.id)
            .order_by(t.SharedResourcePublicationFileRow.path)
        )
        files = (await self._session.execute(stmt)).scalars().all()
        return SharedResourcePublicationAttempt(
            id=row.id,
            shared_resource_id=row.shared_resource_id,
            status=SharedResourcePublicationStatus(row.status),
            description=row.description,
            files=tuple(
                SharedResourceFile(path=file.path, size=file.size, content_hash=file.content_hash)
                for file in files
            ),
            validation_summary=row.validation_summary,
            failure_reason=row.failure_reason,
            version_id=row.version_id,
            created_by=row.created_by,
            created_at=_required(row.created_at),
            started_at=_aware(row.started_at),
            finished_at=_aware(row.finished_at),
        )


class GrantRepositoryImpl:
    """Grant persistence with discriminated-union grantee/target columns."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, grant: Grant) -> None:
        self._session.add(
            t.GrantRow(
                id=grant.id,
                grantor_kind=grant.grantor.kind.value,
                grantor_id=grant.grantor.id,
                grantee_kind=grant.grantee.kind.value,
                grantee_id=grant.grantee.id,
                target_kind=grant.target_kind.value,
                target_id=grant.target_id,
                action=grant.action.value,
                granted_by_id=grant.granted_by,
                created_at=grant.created_at,
            )
        )
        await _flush(self._session)

    async def get(self, grant_id: str) -> Grant | None:
        row = await self._session.get(t.GrantRow, grant_id)
        return _to_grant(row) if row else None

    async def list_for_target(self, target_kind: GrantTargetKind, target_id: str) -> list[Grant]:
        stmt = (
            select(t.GrantRow)
            .where(
                t.GrantRow.target_kind == target_kind.value,
                t.GrantRow.target_id == target_id,
            )
            .order_by(t.GrantRow.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_grant(row) for row in rows]

    async def list_for_grantee(self, grantee: OwnerReference) -> list[Grant]:
        stmt = (
            select(t.GrantRow)
            .where(
                t.GrantRow.grantee_kind == grantee.kind.value,
                t.GrantRow.grantee_id == grantee.id,
            )
            .order_by(t.GrantRow.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_grant(row) for row in rows]

    async def list_for_grantor(self, grantor: OwnerReference) -> list[Grant]:
        stmt = (
            select(t.GrantRow)
            .where(
                t.GrantRow.grantor_kind == grantor.kind.value,
                t.GrantRow.grantor_id == grantor.id,
            )
            .order_by(t.GrantRow.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_grant(row) for row in rows]

    async def delete(self, grant_id: str) -> bool:
        stmt = delete(t.GrantRow).where(t.GrantRow.id == grant_id)
        result = await self._session.execute(stmt)
        await _flush(self._session)
        return result.rowcount > 0

    async def exists_use_grant(
        self,
        grantee: OwnerReference,
        target_kind: GrantTargetKind,
        target_id: str,
        grantor: OwnerReference,
    ) -> bool:
        """Check for a USE Grant from ``grantor`` to ``grantee`` for ``target``.

        Matches either Target == ALL (covering all Grantor assets) or an exact
        (target_kind, target_id) match. The ``grantor`` must equal the asset's
        current Owner — after Ownership transfer, old Grants no longer match.
        """
        stmt = (
            select(t.GrantRow.id)
            .where(
                t.GrantRow.grantor_kind == grantor.kind.value,
                t.GrantRow.grantor_id == grantor.id,
                t.GrantRow.grantee_kind == grantee.kind.value,
                t.GrantRow.grantee_id == grantee.id,
                t.GrantRow.action == GrantAction.USE.value,
                or_(
                    t.GrantRow.target_kind == GrantTargetKind.ALL.value,
                    and_(
                        t.GrantRow.target_kind == target_kind.value,
                        t.GrantRow.target_id == target_id,
                    ),
                ),
            )
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return row is not None


class SqlRepositories:
    """一次工作单元内的全部仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.users = UserRepositoryImpl(session)
        self.user_groups = UserGroupRepositoryImpl(session)
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
        self.run_events = RunEventRepositoryImpl(session)
        self.idempotency = IdempotencyRepositoryImpl(session)
        self.artifacts = ArtifactRepositoryImpl(session)
        self.activities = ActivityRepositoryImpl(session)
        self.notifications = NotificationRepositoryImpl(session)
        self.fork_relations = ForkRelationRepositoryImpl(session)
        self.shared_resources = SharedResourceRepositoryImpl(session)
        self.grants = GrantRepositoryImpl(session)

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def ping(self) -> None:
        await self._session.execute(text("SELECT 1"))


# --------------------------------------------------------------------------
# 行 -> 领域对象
# --------------------------------------------------------------------------


def _asset_discovery_predicate(owner_user_column: Any, owner_group_column: Any, user_id: str):
    active_group_ids = select(t.MembershipRow.user_group_id).where(
        t.MembershipRow.user_id == user_id,
        t.MembershipRow.status == MembershipStatus.ACTIVE.value,
    )
    return (owner_user_column == user_id) | owner_group_column.in_(active_group_ids)


def _shared_resource_discovery_predicate(user_id: str):
    """Owner-scope discovery extended by valid USE Grants (Issue #55).

    A resource is also discoverable when a USE Grant issued under its *current*
    Owner covers it (Target = ALL or the exact resource) and the acting User is
    the grantee personally or an active member of a grantee UserGroup.  Grants
    never add management capability; the guard keeps role resolution owner-scoped.
    """
    active_group_ids = select(t.MembershipRow.user_group_id).where(
        t.MembershipRow.user_id == user_id,
        t.MembershipRow.status == MembershipStatus.ACTIVE.value,
    )
    grantor_matches = (
        (t.GrantRow.grantor_kind == OwnerKind.USER.value)
        & (t.GrantRow.grantor_id == t.SharedResourceRow.owner_user_id)
    ) | (
        (t.GrantRow.grantor_kind == OwnerKind.USER_GROUP.value)
        & (t.GrantRow.grantor_id == t.SharedResourceRow.owner_user_group_id)
    )
    grantee_matches = (
        (t.GrantRow.grantee_kind == OwnerKind.USER.value) & (t.GrantRow.grantee_id == user_id)
    ) | (
        (t.GrantRow.grantee_kind == OwnerKind.USER_GROUP.value)
        & t.GrantRow.grantee_id.in_(active_group_ids)
    )
    target_matches = (t.GrantRow.target_kind == GrantTargetKind.ALL.value) | (
        (t.GrantRow.target_kind == GrantTargetKind.SHARED_RESOURCE.value)
        & (t.GrantRow.target_id == t.SharedResourceRow.id)
    )
    covering_use_grant = select(t.GrantRow.id).where(
        t.GrantRow.action == GrantAction.USE.value,
        grantor_matches,
        grantee_matches,
        target_matches,
    )
    return (
        (t.SharedResourceRow.owner_user_id == user_id)
        | t.SharedResourceRow.owner_user_group_id.in_(active_group_ids)
        | covering_use_grant.exists()
    )


def _owner_reference(owner_user_id: str | None, owner_user_group_id: str | None) -> OwnerReference:
    if owner_user_id is not None and owner_user_group_id is None:
        return OwnerReference(OwnerKind.USER, owner_user_id)
    if owner_user_id is None and owner_user_group_id is not None:
        return OwnerReference(OwnerKind.USER_GROUP, owner_user_group_id)
    raise ValueError("asset row must have exactly one owner")


def _owner_columns(owner: OwnerReference) -> tuple[str | None, str | None]:
    if owner.kind is OwnerKind.USER:
        return owner.id, None
    return None, owner.id


def _to_user(row: t.UserRow) -> User:
    return User(
        id=row.id,
        username=row.username,
        display_name=row.display_name,
        email=row.email,
        created_at=_aware(row.created_at),
    )


def _to_user_group(row: t.UserGroupRow) -> UserGroup:
    return UserGroup(
        id=row.id,
        name=row.name,
        description=row.description,
        created_by_id=row.created_by_id,
        created_at=_aware(row.created_at),
    )


def _to_membership(row: t.MembershipRow) -> Membership:
    return Membership(
        id=row.id,
        user_group_id=row.user_group_id,
        user_id=row.user_id,
        role=MembershipRole(row.role),
        status=MembershipStatus(row.status),
        created_at=_aware(row.created_at),
    )


def _to_project(row: t.ProjectRow) -> Project:
    owner = _owner_reference(row.owner_user_id, row.owner_user_group_id)
    return Project(
        id=row.id,
        name=row.name,
        owner=owner,
        description=row.description,
        status=ProjectStatus(row.status),
        visibility=ProjectVisibility(row.visibility),
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


def _to_environment(row: t.EnvironmentRow) -> Environment:
    return Environment(
        id=row.id,
        name=row.name,
        owner=_owner_reference(row.owner_user_id, row.owner_user_group_id),
        description=row.description,
    )


def _to_environment_version(row: t.EnvironmentVersionRow) -> EnvironmentVersion:
    return EnvironmentVersion(
        id=row.id,
        environment_id=row.environment_id,
        version=row.version,
        description=row.description,
        runtime_kind=EnvironmentRuntimeKind(row.runtime_kind),
        definition=dict(row.definition),
        definition_hash=row.definition_hash,
        execution_spec=dict(row.execution_spec),
        validation_summary=row.validation_summary,
        validation_evidence=dict(row.validation_evidence),
        availability=EnvironmentAvailability(row.availability),
        availability_reason=row.availability_reason,
        availability_detail=row.availability_detail,
        availability_checked_at=_required(row.availability_checked_at),
    )


def _environment_attempt_row(
    attempt: EnvironmentPublicationAttempt,
) -> t.EnvironmentPublicationAttemptRow:
    return t.EnvironmentPublicationAttemptRow(
        id=attempt.id,
        environment_id=attempt.environment_id,
        status=attempt.status.value,
        version=attempt.version,
        description=attempt.description,
        runtime_kind=attempt.runtime_kind.value,
        candidate_definition=attempt.candidate_definition,
        validation_summary=attempt.validation_summary,
        validation_evidence=attempt.validation_evidence,
        failure_code=attempt.failure_code,
        failure_reason=attempt.failure_reason,
        version_id=attempt.version_id,
        created_by=attempt.created_by,
        created_at=attempt.created_at,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
    )


def _to_environment_attempt(
    row: t.EnvironmentPublicationAttemptRow,
) -> EnvironmentPublicationAttempt:
    return EnvironmentPublicationAttempt(
        id=row.id,
        environment_id=row.environment_id,
        status=EnvironmentPublicationStatus(row.status),
        version=row.version,
        description=row.description,
        runtime_kind=EnvironmentRuntimeKind(row.runtime_kind),
        candidate_definition=dict(row.candidate_definition),
        validation_summary=row.validation_summary,
        validation_evidence=dict(row.validation_evidence),
        failure_code=row.failure_code,
        failure_reason=row.failure_reason,
        version_id=row.version_id,
        created_by=row.created_by,
        created_at=_required(row.created_at),
        started_at=row.started_at,
        finished_at=row.finished_at,
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
        user_id=row.user_id,
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
        project_version_id=row.project_version_id,
        project_version_label=row.project_version_label,
        snapshot_id=row.snapshot_id,
        compute_plan_id=row.compute_plan_id,
        source_run_configuration_id=row.source_run_configuration_id,
        source_run_id=row.source_run_id,
        name=row.name,
        status=RunStatus(row.status),
        scheduler_job_id=row.scheduler_job_id,
        exit_code=row.exit_code,
        failure_reason=row.failure_reason,
        initiated_by_user_id=row.initiated_by_user_id,
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


def _to_shared_resource(row: t.SharedResourceRow) -> SharedResource:
    return SharedResource(
        id=row.id,
        name=row.name,
        owner=_owner_reference(row.owner_user_id, row.owner_user_group_id),
        description=row.description,
        created_at=_aware(row.created_at),
    )


def _to_grant(row: t.GrantRow) -> Grant:
    return Grant(
        id=row.id,
        grantor=OwnerReference(OwnerKind(row.grantor_kind), row.grantor_id),
        grantee=OwnerReference(OwnerKind(row.grantee_kind), row.grantee_id),
        target_kind=GrantTargetKind(row.target_kind),
        target_id=row.target_id,
        action=GrantAction(row.action),
        granted_by=row.granted_by_id,
        created_at=_aware(row.created_at),
    )
