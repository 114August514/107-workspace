"""通知的产生与读取。

产生点集中在这里，不下沉到仓储：**每处都要能说清「为什么这个人需要知道」**，
只有用例知道这件事。
"""

from __future__ import annotations

import logging

from ..domain.enums import NotificationType, TargetType
from ..domain.ids import NOTIFICATION, new_id
from ..domain.models import Notification
from ..domain.pagination import Page, PageRequest
from ..domain.ports.clock import Clock
from ..domain.ports.notification import NotificationPublisher
from ..domain.ports.repositories import Repositories
from .activity import SupportsNestedTransaction

logger = logging.getLogger(__name__)


class Notifier:
    """产生通知。

    和 :class:`~workspace107.application.activity.ActivityRecorder` 同一套规矩，
    原因也一样：

    **发不出去不能让用例失败。** 成员已经邀请成功了，不该因为通知写不进去
    而看到报错。所以吞掉异常——但光 try/except 是不够的，写入必须包在
    SAVEPOINT 里，否则 ORM flush 失败会把整个 session 标记成需要回滚，
    请求结束时 commit 抛 PendingRollbackError，主用例的数据一起丢。
    因此通知写入必须放在独立 SAVEPOINT 中。

    **不给自己发通知。** 自己做的事自己知道，通知里全是自己的操作会让
    未读数变成噪音，真正需要关注的反而被淹掉。所以每个产生点都要判断
    收件人是不是操作者本人——这条由 :meth:`_publish` 统一兜底。
    """

    def __init__(
        self,
        publisher: NotificationPublisher,
        clock: Clock,
        session: SupportsNestedTransaction,
    ) -> None:
        self._publisher = publisher
        self._clock = clock
        self._session = session

    async def _publish(
        self,
        *,
        recipient_id: str,
        actor_id: str | None,
        type: NotificationType,
        title: str,
        body: str = "",
        workspace_id: str | None = None,
        target_type: TargetType | None = None,
        target_id: str | None = None,
        mandatory: bool = False,
    ) -> None:
        if actor_id is not None and recipient_id == actor_id:
            # 自己做的事不用通知自己
            return

        notification = Notification(
            id=new_id(NOTIFICATION),
            recipient_id=recipient_id,
            type=type,
            title=title,
            body=body,
            workspace_id=workspace_id,
            target_type=target_type,
            target_id=target_id,
            mandatory=mandatory,
            created_at=self._clock.now(),
        )
        try:
            async with self._session.begin_nested():
                await self._publisher.publish(notification)
        except Exception:
            logger.warning(
                "发送通知失败，已跳过",
                extra={"type": type.value, "recipient_id": recipient_id},
                exc_info=True,
            )

    # -- 成员相关 --------------------------------------------------------

    async def workspace_invited(
        self, *, actor_id: str, invitee_id: str, workspace_id: str, workspace_name: str, role: str
    ) -> None:
        await self._publish(
            recipient_id=invitee_id,
            actor_id=actor_id,
            type=NotificationType.WORKSPACE_INVITED,
            title=f"邀请你加入「{workspace_name}」",
            body=f"角色：{role}。在首页可以接受或拒绝。",
            workspace_id=workspace_id,
            # **不给跳转目标。** 还没接受之前他对这个空间没有访问权，
            # 链到 /workspaces/{id} 只会是 404，因为邀请尚未形成有效成员权限。
            # 处理入口在首页的邀请列表，不在那个空间里。
            #
            # 早先这里链的就是那个空间，正文还写着「在空间列表里可以接受」——
            # 而空间列表只查 ACTIVE，他根本看不到。**通知指向了一个
            # 打不开的页面和一个不存在的入口**，等于没通知。
        )

    async def member_removed(
        self, *, actor_id: str, member_id: str, workspace_id: str, workspace_name: str
    ) -> None:
        await self._publish(
            recipient_id=member_id,
            actor_id=actor_id,
            type=NotificationType.MEMBER_REMOVED,
            title=f"你已被移出「{workspace_name}」",
            body="你不再能访问这个空间里的 Project 和 Run。",
            workspace_id=workspace_id,
            # 不给跳转：他已经看不到这个空间了，链过去只会是 404
            mandatory=True,
        )

    async def role_changed(
        self,
        *,
        actor_id: str,
        member_id: str,
        workspace_id: str,
        workspace_name: str,
        role: str,
    ) -> None:
        await self._publish(
            recipient_id=member_id,
            actor_id=actor_id,
            type=NotificationType.ROLE_CHANGED,
            title=f"你在「{workspace_name}」的角色改为 {role}",
            body="能做什么随之变化，具体以空间页面显示的为准。",
            workspace_id=workspace_id,
            target_type=TargetType.WORKSPACE,
            target_id=workspace_id,
            mandatory=True,
        )

    async def ownership_received(
        self, *, actor_id: str, new_owner_id: str, workspace_id: str, workspace_name: str
    ) -> None:
        await self._publish(
            recipient_id=new_owner_id,
            actor_id=actor_id,
            type=NotificationType.OWNERSHIP_RECEIVED,
            title=f"你成为「{workspace_name}」的所有者",
            body="你现在负责这个空间的成员、配置和资源权益。",
            workspace_id=workspace_id,
            target_type=TargetType.WORKSPACE,
            target_id=workspace_id,
            mandatory=True,
        )

    # -- Run 相关 --------------------------------------------------------

    async def run_finished(
        self,
        *,
        recipient_id: str,
        run_id: str,
        run_name: str,
        workspace_id: str,
        succeeded: bool,
        reason: str = "",
    ) -> None:
        """Run 结束。

        ``actor_id`` 传 None：结束不是谁「做」的，是调度系统的结果。
        所以即使收件人就是提交者本人也要发——**他正是需要知道的那个人**。
        """
        await self._publish(
            recipient_id=recipient_id,
            actor_id=None,
            type=NotificationType.RUN_SUCCEEDED if succeeded else NotificationType.RUN_FAILED,
            title=f"Run {'成功' if succeeded else '失败'}：{run_name}",
            body=reason,
            workspace_id=workspace_id,
            target_type=TargetType.RUN,
            target_id=run_id,
        )

    async def run_submit_failed(
        self, *, recipient_id: str, run_id: str, run_name: str, workspace_id: str, reason: str
    ) -> None:
        await self._publish(
            recipient_id=recipient_id,
            actor_id=None,
            type=NotificationType.RUN_SUBMIT_FAILED,
            title=f"Run 提交失败：{run_name}",
            body=reason,
            workspace_id=workspace_id,
            target_type=TargetType.RUN,
            target_id=run_id,
        )


class NotificationService:
    """读通知、标记已读。

    **不做 Workspace 权限校验，只按收件人过滤。** 通知是发给这个人的，
    与他现在还能不能看见相关对象无关——被移除的成员已经看不到那个空间，
    但「你被移除了」这条必须还能读到，否则他根本不知道发生了什么。

    收件人条件由仓储的每个方法带上，包括标记已读：少一个条件就是
    「能标记别人的通知」这种越权。
    """

    def __init__(self, repos: Repositories, clock: Clock) -> None:
        self._repos = repos
        self._clock = clock

    async def list_for_user(
        self, user_id: str, page: PageRequest, *, unread_only: bool = False
    ) -> Page[Notification]:
        return await self._repos.notifications.list_for_user(user_id, page, unread_only=unread_only)

    async def count_unread(self, user_id: str) -> int:
        return await self._repos.notifications.count_unread(user_id)

    async def mark_read(self, user_id: str, notification_id: str) -> bool:
        return await self._repos.notifications.mark_read(
            user_id, notification_id, self._clock.now()
        )

    async def mark_all_read(self, user_id: str) -> int:
        return await self._repos.notifications.mark_all_read(user_id, self._clock.now())
