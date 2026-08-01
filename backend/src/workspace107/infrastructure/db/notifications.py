"""站内通知：写进数据库，前端轮询。

当前迁移实现只有这一个
:class:`~workspace107.domain.ports.notification.NotificationPublisher` 实现。
后续增加邮件时可以新增组合实现（站内 + 邮件），用例代码不用动。
"""

from __future__ import annotations

from ...domain.models import Notification
from ...domain.ports.repositories import NotificationRepository


class DatabaseNotificationPublisher:
    """把通知写进 notifications 表。

    这里**不做异常处理**。「通知发不出去不能让主用例失败」那条规则由
    application 层的 :class:`~workspace107.application.notifier.Notifier` 统一负责——
    放在这里的话，后续邮件实现就得把同样的逻辑再写一遍，而且写漏了没人发现。
    """

    def __init__(self, notifications: NotificationRepository) -> None:
        self._notifications = notifications

    async def publish(self, notification: Notification) -> None:
        await self._notifications.add(notification)
