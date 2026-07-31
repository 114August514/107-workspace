"""活动记录。

放在 application 层而不是仓储层，因为**只有用例知道这次操作在业务上叫什么**。
仓储只看到「往 runs 表插了一行」，分不清这是「提交 Run」还是「重跑」。

详见 [ADR-0003](../../../../docs/decisions/0003-activity-and-notification.md)。
"""

from __future__ import annotations

import logging
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from ..domain.capabilities import Capability
from ..domain.enums import ActivityAction, TargetType
from ..domain.ids import ACTIVITY, new_id
from ..domain.models import Activity
from ..domain.pagination import Page, PageRequest
from ..domain.ports.clock import Clock
from ..domain.ports.repositories import Repositories
from .access import AccessGuard

logger = logging.getLogger(__name__)


class SupportsNestedTransaction(Protocol):
    """能开启嵌套事务的会话。

    这里只声明用得到的那一个方法，而不是直接依赖 ``AsyncSession``——
    application 层不该认识 SQLAlchemy（见 ADR-0006 的分层规则，
    有测试守着：``tests/unit/test_layering.py``）。
    """

    def begin_nested(self) -> AbstractAsyncContextManager[object]: ...


class ActivityRecorder:
    """把一次已经成功的操作记进活动流。

    两条规则，都不能省：

    **失败的操作不记活动。** 活动流回答「这里发生了什么」，不是审计日志。
    所以调用点一律放在用例成功之后，不要放在 try 里。

    **记活动失败不能让用例失败。** 用户的 Run 已经提交成功了，
    不该因为活动表写不进去而看到报错。

    第二条有个坑：光 try/except 吞掉异常是**不够**的。仓储用的是 ORM 的
    ``add`` + ``flush``，flush 失败会把整个 session 标记成需要回滚，
    之后请求结束时的 commit 会抛 PendingRollbackError——
    **主用例的数据会一起丢掉**，正好是这条规则想避免的事。
    所以写入包在 SAVEPOINT 里，失败只回滚这一小段。

    这两种做法的差别验证过（``tests/integration/test_activity.py``）：
    不加 SAVEPOINT 时主用例数据确实会丢。
    """

    def __init__(
        self,
        repos: Repositories,
        clock: Clock,
        session: SupportsNestedTransaction,
    ) -> None:
        self._repos = repos
        self._clock = clock
        self._session = session

    async def record(
        self,
        *,
        actor_id: str,
        workspace_id: str,
        action: ActivityAction,
        target_type: TargetType,
        target_id: str,
        target_name: str,
        project_id: str | None = None,
        detail: str = "",
    ) -> None:
        try:
            async with self._session.begin_nested():
                actor = await self._repos.users.get(actor_id)
                activity = Activity(
                    id=new_id(ACTIVITY),
                    workspace_id=workspace_id,
                    project_id=project_id,
                    actor_id=actor_id,
                    # 用户名在这里抄一份存起来。查名字这一步也放在 SAVEPOINT 里，
                    # 因为它同样是「为了记活动」而做的事，失败了不该牵连主用例。
                    actor_name=actor.username if actor else actor_id,
                    action=action,
                    target_type=target_type,
                    target_id=target_id,
                    target_name=target_name,
                    detail=detail,
                    created_at=self._clock.now(),
                )
                await self._repos.activities.add(activity)
        except Exception:
            # 记下来但不往上抛。活动流少一条，比用户的操作失败要好得多。
            logger.warning(
                "写入活动失败，已跳过",
                extra={"action": action.value, "workspace_id": workspace_id},
                exc_info=True,
            )


class ActivityService:
    """读活动流。

    和 :class:`ActivityRecorder` 分开：Recorder 是写侧，被注入到各个用例里；
    这个是读侧，直接暴露给路由。两者依赖不同（Recorder 需要 session 开
    SAVEPOINT，读侧不需要），职责也不同，合成一个类只会让构造函数变长。

    **没有单独的「查看活动」能力。** 活动回答的是「这个空间里发生了什么」，
    能看见这个空间的人就该看得见——包括 Viewer，他们本来就是来观摩的。
    所以直接复用 WORKSPACE_VIEW / PROJECT_VIEW（见 ADR-0008 的能力矩阵）。
    """

    def __init__(self, repos: Repositories, guard: AccessGuard) -> None:
        self._repos = repos
        self._guard = guard

    async def list_for_workspace(
        self, user_id: str, workspace_id: str, page: PageRequest
    ) -> Page[Activity]:
        await self._guard.workspace(user_id, workspace_id, needs=Capability.WORKSPACE_VIEW)
        return await self._repos.activities.list_for_workspace(workspace_id, page)

    async def list_for_project(
        self, user_id: str, project_id: str, page: PageRequest
    ) -> Page[Activity]:
        await self._guard.project(user_id, project_id, needs=Capability.PROJECT_VIEW)
        return await self._repos.activities.list_for_project(project_id, page)
