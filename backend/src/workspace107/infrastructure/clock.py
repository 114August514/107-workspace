"""系统时钟。"""

from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """真实时钟。测试里换成可控实现即可冻结时间线。"""

    def now(self) -> datetime:
        return datetime.now(UTC)
