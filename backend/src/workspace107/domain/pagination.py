"""分页。

**不是所有列表都要分页。** 判断标准是「规模由什么决定」：

    历史类：随时间单调增长，用一天就多一批
    → Run、Project Version、Project —— 必须分页

    状态类：由当前状态决定规模，删掉就少了
    → 项目文件、成员、变量、运行方案、算力方案 —— 返回数组

给状态类硬套分页只会让文件树、成员列表这种本来该一次看全的东西变难用；
给历史类不分页则是等着某一天它把接口拖垮。

分页模型全站只有这一种。真的需要游标分页时（比如活动流需要稳定的
无限滚动），应当**新增一种明确命名的模型**，而不是把这一种悄悄改掉——
改掉的话所有已经在用它的地方都要跟着改。
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ValidationFailed

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 200


@dataclass(frozen=True, slots=True)
class PageRequest:
    """一次分页查询的请求。"""

    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValidationFailed("页码从 1 开始")
        if not 1 <= self.page_size <= MAX_PAGE_SIZE:
            raise ValidationFailed(f"每页条数应在 1 到 {MAX_PAGE_SIZE} 之间")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True)
class Page[T]:
    """一页结果。

    带上 ``total`` 是为了让界面能显示总数和页码。代价是每次查询多一次 count，
    对目前的数据量完全可以接受；真到了 count 变慢的规模，说明也该换游标分页了。
    """

    items: list[T]
    page: int
    page_size: int
    total: int

    @property
    def has_more(self) -> bool:
        return self.page * self.page_size < self.total

    @classmethod
    def empty(cls, request: PageRequest) -> Page[T]:
        return cls(items=[], page=request.page, page_size=request.page_size, total=0)
