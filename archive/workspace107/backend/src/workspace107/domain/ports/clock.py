"""时钟端口。

时间从端口取而不是直接调用 ``datetime.now()``，测试才能控制时间线。
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """返回当前时间（带时区）。"""
        ...
