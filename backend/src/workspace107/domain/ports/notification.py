"""通知发布端口。

当前迁移实现只有一个发布方式：写进数据库，由前端轮询未读数。保留这个端口，
是为了以后增加邮件等送达方式时只新增组合实现，不改动各个通知产生点。

如果现在到处直接 `repos.notifications.add(...)`，将来增加送达方式就得把每个
产生点都翻出来改一遍，还容易漏。
"""

from __future__ import annotations

from typing import Protocol

from ..models import Notification


class NotificationPublisher(Protocol):
    """把一条通知送到收件人。

    实现方决定「送」是什么意思：当前是写库，后续可以组合邮件等外部渠道。
    调用方只负责说清楚「谁需要知道什么」。
    """

    async def publish(self, notification: Notification) -> None: ...
