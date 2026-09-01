"""通知的产生与读取。

产生点集中在这里，不下沉到仓储：**每处都要能说清「为什么这个人需要知道」**，
只有用例知道这件事。
"""

from __future__ import annotations

import logging

from ..domain.enums import NotificationType, TargetType
from ..domain.errors import ValidationFailed
from ..domain.ids import NOTIFICATION, new_id
from ..domain.models import Notification
from ..domain.pagination import Page, PageRequest
from ..domain.ports.clock import Clock
from ..domain.ports.notification import NotificationPublisher
from ..domain.ports.repositories import NotificationRepository, Repositories
from .activity import SupportsNestedTransaction

logger = logging.getLogger(__name__)

MANDATORY_NOTIFICATION_TYPES = frozenset(
    {
        NotificationType.MEMBER_REMOVED,
        NotificationType.ROLE_CHANGED,
        NotificationType.OWNERSHIP_RECEIVED,
        NotificationType.ENVIRONMENT_UNAVAILABLE,
        NotificationType.SHARED_RESOURCE_UNAVAILABLE,
        NotificationType.PLATFORM_INCIDENT,
    }
)


class Notifier:
    """Create recipient-scoped in-app notifications."""

    def __init__(
        self,
        publisher: NotificationPublisher,
        clock: Clock,
        session: SupportsNestedTransaction,
        preferences: NotificationRepository | None = None,
    ) -> None:
        self._publisher = publisher
        self._clock = clock
        self._session = session
        self._preferences = preferences

    async def _publish(
        self,
        *,
        recipient_id: str,
        actor_id: str | None,
        type: NotificationType,
        title: str,
        body: str = "",
        target_type: TargetType | None = None,
        target_id: str | None = None,
        mandatory: bool = False,
    ) -> None:
        if actor_id is not None and recipient_id == actor_id:
            return
        mandatory = mandatory or type in MANDATORY_NOTIFICATION_TYPES
        if (
            not mandatory
            and self._preferences is not None
            and not await self._preferences.is_enabled(recipient_id, type)
        ):
            return
        notification = Notification(
            id=new_id(NOTIFICATION),
            recipient_id=recipient_id,
            type=type,
            title=title,
            body=body,
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

    async def user_group_invited(
        self, *, actor_id: str, invitee_id: str, user_group_id: str, user_group_name: str, role: str
    ) -> None:
        await self._publish(
            recipient_id=invitee_id,
            actor_id=actor_id,
            type=NotificationType.USER_GROUP_INVITED,
            title=f"邀请你加入「{user_group_name}」",
            body=f"角色：{role}。在首页可以接受或拒绝。",
        )

    async def member_removed(
        self, *, actor_id: str, member_id: str, user_group_id: str, user_group_name: str
    ) -> None:
        await self._publish(
            recipient_id=member_id,
            actor_id=actor_id,
            type=NotificationType.MEMBER_REMOVED,
            title=f"你已被移出「{user_group_name}」",
            body="你不再能访问这个 User Group 拥有的对象。",
            mandatory=True,
        )

    async def role_changed(
        self, *, actor_id: str, member_id: str, user_group_id: str, user_group_name: str, role: str
    ) -> None:
        await self._publish(
            recipient_id=member_id,
            actor_id=actor_id,
            type=NotificationType.ROLE_CHANGED,
            title=f"你在「{user_group_name}」的角色改为 {role}",
            body="能做什么随之变化，具体以 User Group 页面为准。",
            target_type=TargetType.USER_GROUP,
            target_id=user_group_id,
            mandatory=True,
        )

    async def ownership_received(
        self, *, actor_id: str, new_owner_id: str, user_group_id: str, user_group_name: str
    ) -> None:
        await self._publish(
            recipient_id=new_owner_id,
            actor_id=actor_id,
            type=NotificationType.OWNERSHIP_RECEIVED,
            title=f"你成为「{user_group_name}」的 Owner",
            body="你现在负责这个 User Group 的成员与治理。",
            target_type=TargetType.USER_GROUP,
            target_id=user_group_id,
            mandatory=True,
        )

    async def run_finished(
        self, *, recipient_id: str, run_id: str, run_name: str, succeeded: bool, reason: str = ""
    ) -> None:
        await self._publish(
            recipient_id=recipient_id,
            actor_id=None,
            type=NotificationType.RUN_SUCCEEDED if succeeded else NotificationType.RUN_FAILED,
            title=f"Run {'成功' if succeeded else '失败'}：{run_name}",
            body=reason,
            target_type=TargetType.RUN,
            target_id=run_id,
        )

    async def run_submit_failed(
        self, *, recipient_id: str, run_id: str, run_name: str, reason: str
    ) -> None:
        await self._publish(
            recipient_id=recipient_id,
            actor_id=None,
            type=NotificationType.RUN_SUBMIT_FAILED,
            title=f"Run 提交失败：{run_name}",
            body=reason,
            target_type=TargetType.RUN,
            target_id=run_id,
        )

    async def asset_unavailable(
        self,
        *,
        recipient_id: str,
        project_id: str,
        project_name: str,
        type: NotificationType,
        asset_label: str,
        detail: str,
    ) -> None:
        if type not in {
            NotificationType.ENVIRONMENT_UNAVAILABLE,
            NotificationType.SHARED_RESOURCE_UNAVAILABLE,
        }:
            raise ValidationFailed("不可用资产通知必须使用资产不可用类别")
        await self._publish(
            recipient_id=recipient_id,
            actor_id=None,
            type=type,
            title=f"Project「{project_name}」依赖不可用：{asset_label}",
            body=detail,
            target_type=TargetType.PROJECT,
            target_id=project_id,
            mandatory=True,
        )

    async def environment_unavailable(
        self,
        *,
        recipient_id: str,
        project_id: str,
        project_name: str,
        asset_label: str,
        detail: str,
    ) -> None:
        await self.asset_unavailable(
            recipient_id=recipient_id,
            project_id=project_id,
            project_name=project_name,
            type=NotificationType.ENVIRONMENT_UNAVAILABLE,
            asset_label=asset_label,
            detail=detail,
        )

    async def shared_resource_unavailable(
        self,
        *,
        recipient_id: str,
        project_id: str,
        project_name: str,
        asset_label: str,
        detail: str,
    ) -> None:
        await self.asset_unavailable(
            recipient_id=recipient_id,
            project_id=project_id,
            project_name=project_name,
            type=NotificationType.SHARED_RESOURCE_UNAVAILABLE,
            asset_label=asset_label,
            detail=detail,
        )

    async def platform_incident(self, *, recipient_id: str, title: str, body: str) -> None:
        await self._publish(
            recipient_id=recipient_id,
            actor_id=None,
            type=NotificationType.PLATFORM_INCIDENT,
            title=title,
            body=body,
            mandatory=True,
        )


class NotificationService:
    """Read and mutate recipient-scoped notifications and preferences."""

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

    async def mark_unread(self, user_id: str, notification_id: str) -> bool:
        return await self._repos.notifications.mark_unread(user_id, notification_id)

    async def mark_all_read(self, user_id: str) -> int:
        return await self._repos.notifications.mark_all_read(user_id, self._clock.now())

    async def list_preferences(self, user_id: str) -> dict[NotificationType, bool]:
        stored = {
            preference.type: preference.enabled
            for preference in await self._repos.notifications.list_preferences(user_id)
        }
        return {type: stored.get(type, True) for type in NotificationType}

    async def set_preference(self, user_id: str, type: NotificationType, enabled: bool) -> bool:
        if type in MANDATORY_NOTIFICATION_TYPES and not enabled:
            raise ValidationFailed("重要系统通知不能关闭")
        preference = await self._repos.notifications.set_preference(user_id, type, enabled)
        return preference.enabled
