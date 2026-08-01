"""通知发布端口。

M2 只有一个实现——写进数据库，前端轮询未读数。留这个端口的**唯一理由**
是 V1 要加邮件：到时候新增一个组合实现（站内 + 邮件），用例代码一行都不用改。

如果现在到处直接 `repos.notifications.add(...)`，将来加邮件就得把每个产生点
都翻出来改一遍，还容易漏。见 [ADR-0003](
../../../../../docs/decisions/0003-activity-and-notification.md) 第 3 节。
"""

from __future__ import annotations

from typing import Protocol

from ..models import Notification


class NotificationPublisher(Protocol):
    """把一条通知送到收件人。

    实现方决定「送」是什么意思：M2 是写库，V1 可能同时发邮件。
    调用方只负责说清楚「谁需要知道什么」。
    """

    async def publish(self, notification: Notification) -> None: ...
