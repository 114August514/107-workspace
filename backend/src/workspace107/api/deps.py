"""依赖注入。

进程级单例（存储、调度器、时钟、数据库引擎）放在 ``AppContext`` 里；
仓储和用例服务按请求创建，事务边界就是一次请求。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from ..application.access import AccessGuard
from ..application.activity import ActivityRecorder, ActivityService
from ..application.catalog_service import CatalogService
from ..application.configuration_service import ConfigurationService
from ..application.entitlement_service import EntitlementService
from ..application.environment_service import EnvironmentPublicationService
from ..application.grant_service import GrantService
from ..application.health_service import HealthService
from ..application.identity_service import IdentityService
from ..application.notifier import NotificationService, Notifier
from ..application.project_service import ProjectService
from ..application.run_configuration_service import RunConfigurationService
from ..application.run_lifecycle import RunLifecycleService
from ..application.run_service import RunService
from ..application.scoped_config_resolver import ScopedConfigResolver
from ..application.shared_resource_publication import SharedResourcePublicationProcessor
from ..application.shared_resource_service import SharedResourceService
from ..application.user_group_service import UserGroupService
from ..config import Settings
from ..domain.models import User
from ..domain.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, PageRequest
from ..domain.ports.clock import Clock
from ..domain.ports.notification import NotificationPublisher
from ..domain.ports.repositories import Repositories
from ..domain.ports.scheduler import SchedulerPort
from ..domain.ports.secret_vault import SecretVault
from ..domain.ports.storage import StoragePort
from ..domain.slurm_projection import SlurmProjection
from ..infrastructure.db.notifications import DatabaseNotificationPublisher
from ..infrastructure.db.repositories import SqlRepositories
from ..infrastructure.db.secret_vault import DatabaseSecretVault

DEV_USER_HEADER = "X-User"
DEFAULT_DEV_USER = "student"


@dataclass(slots=True)
class AppContext:
    """进程级依赖。"""

    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    storage: StoragePort
    scheduler: SchedulerPort
    slurm_projection: SlurmProjection | None
    clock: Clock


@dataclass(slots=True)
class Services:
    """一次请求内可用的用例服务。

    这里**只有 application 层的服务**。路由拿不到仓储、存储和调度器，
    所以也没办法绕过用例层直接操作基础设施——权限校验、事务边界和领域规则
    都在服务里，绕过去就等于绕过它们。

    需要新增一类操作时，加一个用例服务或给现有服务加方法，
    不要往这个容器里塞端口。
    """

    identity: IdentityService
    user_groups: UserGroupService
    configuration: ConfigurationService
    entitlements: EntitlementService
    projects: ProjectService
    run_configurations: RunConfigurationService
    runs: RunService
    catalog: CatalogService
    environment_publications: EnvironmentPublicationService
    health: HealthService
    lifecycle: RunLifecycleService
    activities: ActivityService
    notifications: NotificationService
    shared_resources: SharedResourceService
    shared_resource_publications: SharedResourcePublicationProcessor
    grants: GrantService


def build_services(context: AppContext, session: AsyncSession) -> Services:
    """组装一次请求的用例服务。

    这是除 ``main.build_context`` 之外唯一的装配点：
    在这里把具体实现注入到用例，用例本身只认 domain 的端口协议。
    """
    repos: Repositories = SqlRepositories(session)
    vault: SecretVault = DatabaseSecretVault(session)
    guard = AccessGuard(repos)
    # 活动记录需要开 SAVEPOINT，所以这里把 session 传进去。
    # 用例层只认 SupportsNestedTransaction 那一个方法，不认识 SQLAlchemy。
    activity = ActivityRecorder(repos, context.clock, session)
    # 通知的出口只有这一个端口。以后增加邮件时换成组合实现（站内 + 邮件），
    # 各个用例里的调用不需要改变；端口就是为了隔离具体送达方式。
    publisher: NotificationPublisher = DatabaseNotificationPublisher(repos.notifications)
    notifier = Notifier(publisher, context.clock, session)

    return Services(
        identity=IdentityService(repos, context.clock, session),
        user_groups=UserGroupService(repos, guard, context.clock, activity, notifier),
        configuration=ConfigurationService(repos, guard, vault),
        entitlements=EntitlementService(repos),
        projects=ProjectService(
            repos,
            guard,
            context.clock,
            context.storage,
            activity,
            max_file_bytes=context.settings.max_file_bytes,
            max_archive_total_bytes=context.settings.max_archive_total_bytes,
            max_archive_entries=context.settings.max_archive_entries,
        ),
        run_configurations=RunConfigurationService(repos, guard),
        runs=RunService(
            repos,
            guard,
            context.clock,
            context.storage,
            context.scheduler,
            context.slurm_projection,
            vault,
            activity,
            notifier,
            config_resolver=ScopedConfigResolver(repos.variables, vault),
        ),
        catalog=CatalogService(repos, guard),
        environment_publications=EnvironmentPublicationService(
            repos, guard, context.storage, context.clock
        ),
        health=HealthService(repos),
        lifecycle=RunLifecycleService(
            repos, context.clock, context.storage, context.scheduler, activity, notifier, session
        ),
        notifications=NotificationService(repos, context.clock),
        activities=ActivityService(repos, guard),
        shared_resources=SharedResourceService(
            repos,
            guard,
            context.clock,
            context.storage,
            activity,
            max_file_bytes=context.settings.max_file_bytes,
        ),
        shared_resource_publications=SharedResourcePublicationProcessor(
            repos,
            context.clock,
            context.storage,
            activity,
            recovery_seconds=context.settings.shared_resource_publication_recovery_seconds,
        ),
        grants=GrantService(repos, guard, context.clock),
    )


def get_context(request: Request) -> AppContext:
    return request.app.state.context  # type: ignore[no-any-return]


async def get_services(
    context: Annotated[AppContext, Depends(get_context)],
) -> AsyncIterator[Services]:
    session = context.session_factory()
    try:
        yield build_services(context, session)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_current_user(
    services: Annotated[Services, Depends(get_services)],
    x_user: Annotated[str | None, Header(alias=DEV_USER_HEADER)] = None,
) -> User:
    """Resolve the dev identity without creating any ownership container."""
    username = (x_user or DEFAULT_DEV_USER).strip() or DEFAULT_DEV_USER
    return await services.identity.ensure_user(username)


def get_page(
    page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=MAX_PAGE_SIZE, description="每页条数")
    ] = DEFAULT_PAGE_SIZE,
) -> PageRequest:
    return PageRequest(page=page, page_size=page_size)


ServicesDep = Annotated[Services, Depends(get_services)]
CurrentUser = Annotated[User, Depends(get_current_user)]
ContextDep = Annotated[AppContext, Depends(get_context)]
PageDep = Annotated[PageRequest, Depends(get_page)]
